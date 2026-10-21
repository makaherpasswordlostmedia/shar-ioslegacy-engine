#!/usr/bin/env python3
"""Композиция radmusic (.rms: sound/ambience/ambience.rms, sound/music/l<N>_music.rms) — разбор по данным диска.

  python3 tools/rms.py sound/ambience/ambience.rms      события -> регионы -> потоки -> файлы .rsd (печать)

Формат выведен из самого файла (схема полей лежит в нём же, в заголовке; своих догадок о смысле нет, только чтение):
  u32 n, u32 0, n x u32               таблица правок указателей образа памяти (здесь не нужна)
  схема                               описания типов radmusic_comp, group, region, layer, … с именами полей
  часть 1 (после строки 'event_ref')  объект comp: u32 sound_memory_max, cache_memory_max, stream_size_min, 36 x u32 адрес
                                      массива; затем 36 массивов в том же порядке (ARRAYS): u32 count, u32 размер элемента в
                                      памяти, count элементов подряд — поля по схеме (ARRAYS): u32/f32/адрес — 4 Б, bool — 1 Б,
                                      вложенная структура — её поля подряд; строки и массивы — адрес хранилища (u32)
  часть 2                             имя композиции (строка), затем содержимое хранилищ строк и массивов ПО ВОЗРАСТАНИЮ
                                      адреса: строка — байты до 0; массив — u32 count, u32 размер элемента, count x u32
Адрес объекта пула = адрес массива + 0x40 + индекс x размер элемента. Проверки разбора (иначе исключение): после части 1
стоит имя композиции (печатная строка), каждое хранилище прочитано один раз, часть 2 кончается ровно на конце файла.

Цепочка звука: событие -> action_arrays -> play_region/push_region/pop_region -> регион -> layer_refs -> слой ->
sequence_ref -> root_event -> дерево событий (logic_repeat.event_ref, logic_and/logic_or.events) -> event_stream.stream_ref ->
поток -> rsd_file_ref -> имя файла. Проверено на ambience.rms: события-заглушки Placeholder4/5 (id 57/58 локаторов cemetary*)
ведут в cemetary_day/night_region, Placeholder7 (ufo_ambience_*) — в halloween_ufo_ambience_region."""
import heapq, struct, sys

# массивы comp в порядке полей; элемент: u — u32, f — f32, b — bool (1 Б), r — ссылка на объект пула, S — адрес строки,
# A — адрес массива (u32 элементы), X — адрес массива адресов массивов (event.action_arrays), V — адрес массива адресов строк
ARRAYS = [
    ('groups', 'SAAAAru'),            # name, children, stream_refs, clip_refs, region_refs, parent_ref, tree_depth
    ('fade_transitions', 'rrffffA'),  # source_region_ref, target_region_ref, source_time, source_start, target_time, target_start, beat_set.beats
    ('stitch_transitions', 'rrr'),    # source_region_ref, target_region_ref, transition_region_ref
    ('events', 'SXr'),                # name, action_arrays, event_matrix_ref
    ('event_matricies', 'A'),         # state_ref_array
    ('states', 'SV'),                 # name, values (массив адресов строк: Stage1, Stage2 …)
    ('rsd_files', 'Suuuuu'),          # file_name, size, audio_format{encoding, channels, bit_resolution, sampling_rate}
    ('streams', 'Srrbffuu'),          # name, parent_group_ref, rsd_file_ref, streamed, tempo_track{bpm, start_beat, num, den}
    ('clips', 'Srrffuu'),             # name, parent_group_ref, rsd_file_ref, tempo_track
    ('regions', 'SArrf'),             # name, layer_refs, exit_region_ref, group_ref, volume
    ('sequences', 'ru'),              # root_event, stack_size
    ('layers', 'SbArf'),              # name, constant, beat_set.beats, sequence_ref, volume
    ('event_clip', 'ur'), ('event_stream', 'ur'), ('event_silence', 'uff'),
    ('var_volume', 'uf'), ('var_pitch', 'uf'), ('var_volume_rand_min', 'uf'), ('var_volume_rand_max', 'uf'),
    ('var_pitch_rand_min', 'uf'), ('var_pitch_rand_max', 'uf'), ('var_aux_gain', 'uuf'), ('var_positional', 'ub'),
    ('var_pos_fall_off', 'uf'), ('var_pos_dist_min', 'uf'), ('var_pos_dist_max', 'uf'), ('callback', 'uS'),
    ('logic_and', 'uA'), ('logic_or', 'uA'), ('logic_repeat', 'uuur'),   # logic_repeat: type, min_times, max_times, event_ref
    ('play_region', 'uru'),           # type, region_ref, region_resume_type
    ('push_region', 'uruu'),          # type, region_ref, target_region_resume_type, current_region_resume_type
    ('pop_region', 'ur'), ('start_layer', 'uS'), ('stop_layer', 'uS'), ('rand_state', 'ur'),
]
NULL = 0xffffffff


class Comp:
    def __init__(self, data):
        b = bytes(data)
        o = b.index(b'event_ref\x00') + 10                      # конец схемы: последнее имя поля
        self.memory = struct.unpack_from('<3I', b, o); o += 12
        heads = struct.unpack_from('<%dI' % len(ARRAYS), b, o); o += 4 * len(ARRAYS)
        self.pools, ptrs = {}, []                               # ptrs: (адрес хранилища, вид S/A/X)
        for (name, spec), head in zip(ARRAYS, heads):
            n, size = struct.unpack_from('<II', b, o); o += 8
            els = []
            for _ in range(n):
                e = []
                for k in spec:
                    if k == 'b': e.append(b[o]); o += 1; continue
                    v = struct.unpack_from('<f' if k == 'f' else '<I', b, o)[0]; o += 4
                    if k in 'rSAXV' and v == NULL: v = None
                    if k in 'SAXV' and v is not None: ptrs.append((v, k))
                    e.append(v)
                els.append(e)
            self.pools[name] = dict(base=head + 0x40, size=size, els=els)
        # часть 2: имя композиции, затем хранилища по возрастанию адреса
        e = b.index(b'\0', o); self.name = b[o:e].decode('latin-1'); o = e + 1
        if not self.name or not self.name.isprintable(): raise ValueError('rms: часть 1 разобрана неверно (имя %r)' % self.name)
        self.store = {}
        work = sorted(set(ptrs))
        heapq.heapify(work)
        while work:
            addr, kind = heapq.heappop(work)
            if addr in self.store: raise ValueError('rms: хранилище %x дважды' % addr)
            if kind == 'S':
                e = b.index(b'\0', o); self.store[addr] = b[o:e].decode('latin-1'); o = e + 1; continue
            n, _ = struct.unpack_from('<II', b, o)
            vals = list(struct.unpack_from('<%dI' % n, b, o + 8)); o += 8 + 4 * n
            self.store[addr] = vals
            if kind in 'XV':                                   # адреса внутренних массивов / строк (выше внешнего) — в очередь
                for v in vals:
                    if v <= addr: raise ValueError('rms: внутренний массив %x ниже внешнего %x' % (v, addr))
                    heapq.heappush(work, (v, 'A' if kind == 'X' else 'S'))
        if o != len(b): raise ValueError('rms: часть 2 разобрана до %d из %d' % (o, len(b)))

    def owner(self, addr):
        """адрес -> (пул, индекс) или None"""
        if addr is None: return None
        for name, p in self.pools.items():
            n = len(p['els'])
            if n and p['base'] <= addr < p['base'] + p['size'] * n and (addr - p['base']) % p['size'] == 0:
                return name, (addr - p['base']) // p['size']
        return None

    def el(self, addr):
        name, i = self.owner(addr); return name, i, self.pools[name]['els'][i]

    # ------------------------------------------------------------------ удобные виды
    def stream_file(self, si):
        """поток -> (имя потока, имя файла .rsd без пути и расширения)"""
        s = self.pools['streams']['els'][si]
        return self.store[s[0]], self.store[self.el(s[2])[2][0]]

    def event_streams(self, addr):
        """дерево событий -> [[индексы потоков-альтернатив], ...] в порядке проигрывания (logic_or — альтернативы)"""
        name, i, e = self.el(addr)
        if name == 'event_stream': return [[self.owner(e[1])[1]]]
        if name == 'logic_repeat': return self.event_streams(e[3])
        if name == 'logic_and': return [x for r in self.store[e[1]] for x in self.event_streams(r)]
        if name == 'logic_or': return [[s for r in self.store[e[1]] for alt in self.event_streams(r) for s in alt]]
        return []                                              # тишина, громкость, callback …

    def event_plan(self, addr, rep=False):
        """дерево событий -> [(в повторе?, [потоки-альтернативы])] в порядке проигрывания: logic_and — по очереди,
        logic_repeat — всё внутри повторяется, logic_or — выбор одного из (альтернативы)"""
        name, i, e = self.el(addr)
        if name == 'event_stream': return [(rep, [self.owner(e[1])[1]])]
        if name == 'logic_repeat': return self.event_plan(e[3], True)
        if name == 'logic_and': return [x for r in self.store[e[1]] for x in self.event_plan(r, rep)]
        if name == 'logic_or': return [(rep, [s for r in self.store[e[1]] for _, alt in self.event_plan(r, rep) for s in alt])]
        return []

    def region_plan(self, ri):
        r = self.pools['regions']['els'][ri]; out = []
        for la in self.store[r[1]]:
            out += self.event_plan(self.el(self.el(la)[2][3])[2][0])
        return out

    def region_index(self, name):
        return next((i for i in range(len(self.pools['regions']['els'])) if self.region_name(i) == name), None)

    def region_streams(self, ri):
        """регион -> [[потоки-альтернативы], ...] по слоям"""
        r = self.pools['regions']['els'][ri]; out = []
        for la in self.store[r[1]]:
            seq = self.el(self.el(la)[2][3])[2]
            out += self.event_streams(seq[0])
        return out

    def region_name(self, ri): return self.store[self.pools['regions']['els'][ri][0]]

    def events(self):
        """[(имя события, [(вид действия play_region/push_region/pop_region, индекс региона или None)])]"""
        out = []
        for e in self.pools['events']['els']:
            acts = []
            for arr in self.store[e[1]]:
                for a in self.store[arr]:
                    kind, _, ae = self.el(a)
                    reg = self.owner(ae[1]) if kind in ('play_region', 'push_region', 'pop_region') else None
                    acts.append((kind, reg[1] if reg and reg[0] == 'regions' else None))
            out.append((self.store[e[0]], acts))
        return out


def read(path):
    with open(path, 'rb') as f: return Comp(f.read())


if __name__ == '__main__':
    C = read(sys.argv[1])
    print('композиция', C.name, {k: len(p['els']) for k, p in C.pools.items() if p['els']})
    for name, acts in C.events():
        desc = []
        for kind, ri in acts:
            files = [[C.stream_file(s)[1] for s in alt] for alt in C.region_streams(ri)] if ri is not None else []
            desc.append('%s %s %s' % (kind, C.region_name(ri) if ri is not None else '-', files))
        print('%-32s %s' % (name, '; '.join(desc)))
