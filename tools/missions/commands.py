"""Command table for SHAR mission scripts (.mfk).

Single source of truth for: opcode numbers (stable, = donut/dev/codegen/cmd.json order, 1-based),
argument signatures (donut spec, GPL reimplementation = public command registry of the game),
our semantics (meaning), which engine feature implements it, when the runtime runs it, and
which arguments are locator names (resolved at compile time).

route:
  'rt'   - consumed by the mission runtime itself (structure, objective/condition parameters)
  'eng'  - forwarded to the engine via MsnHost.command() (spawns, loads, cameras, music ...)
  'both' - runtime reads it AND forwards it (e.g. AddNPC: runtime remembers where the NPC stands)
when:
  'start' - executed when its block starts (stage enter / objective start / level load)
  'end'   - executed when the stage completes (fade out, car swap, completion line ...)
replay: re-sent (when = MSN_AT_REPLAY) for stages before the checkpoint on retry,
        so that vehicles / NPCs / props spawned by earlier stages exist again.
"""
import json
from pathlib import Path

# Frozen opcode order (donut cmd.json order). Append-only: never reorder.
OPCODE_ORDER = ['HelloWorld', 'LoadP3DFile', 'SetParticleTexture', 'BindReward', 'SetCarAttributes', 'SetTotalGags', 'SelectMission', 'SetMissionResetPlayerInCar', 'SetDynaLoadData', 'UsePedGroup', 'AddStage', 'SetPresentationBitmap', 'SetStageMessageIndex', 'AddObjective', 'SetObjTargetVehicle', 'CloseObjective', 'CloseStage', 'RESET_TO_HERE', 'SetHUDIcon', 'AddCollectible', 'SetStageTime', 'AddCondition', 'CloseCondition', 'ShowStageComplete', 'AddNPC', 'SetDestination', 'SetCollectibleEffect', 'AddStageTime', 'AddObjectiveNPCWaypoint', 'SetTalkToTarget', 'SetDialogueInfo', 'SetCamBestSide', 'CloseMission', 'PlacePlayerCar', 'SetMaxTraffic', 'AddStageVehicle', 'AddStageWaypoint', 'SetRaceLaps', 'SetDemoLoopTime', 'AddStageMusicChange', 'LoadDisposableCar', 'AddMission', 'ClearGagBindings', 'GagBegin', 'GagSetInterior', 'GagSetCycle', 'GagSetPosition', 'GagSetRandom', 'GagSetSound', 'GagSetTrigger', 'GagEnd', 'GagSetSparkle', 'GagSetPersist', 'GagSetCoins', 'GagSetAnimCollision', 'GagSetIntro', 'GagSetOutro', 'GagSetCameraShake', 'GagPlayFMV', 'EnableTutorialMode', 'InitLevelPlayerVehicle', 'AddCharacter', 'CreateChaseManager', 'SetHitAndRunDecay', 'SetNumChaseCars', 'AddNPCCharacterBonusMission', 'AddBonusMissionNPCWaypoint', 'AddAmbientCharacter', 'AddAmbientNPCWaypoint', 'AddPurchaseCarReward', 'AddPurchaseCarNPCWaypoint', 'CreateTrafficGroup', 'AddTrafficModel', 'CloseTrafficGroup', 'CreatePedGroup', 'AddPed', 'ClosePedGroup', 'PreallocateActors', 'SetProjectileStats', 'AddSpawnPointByLocatorScript', 'AddBehaviour', 'SetActorRotationSpeed', 'SetAnimatedCameraName', 'SetAnimCamMulticontName', 'SetCoinFee', 'PutMFPlayerInCar', 'StartCountdown', 'AddToCountdownSequence', 'UseElapsedTime', 'SetRaceEnteryFee', 'SetParTime', 'SetCondMinHealth', 'SetCondTargetVehicle', 'SetCondTime', 'AddBonusMission', 'AddTeleportDest', 'AddVehicleSelectInfo', 'SuppressDriver', 'SetBonusMissionDialoguePos', 'SetConversationCam', 'ClearAmbientAnimations', 'AddAmbientNpcAnimation', 'AddAmbientPcAnimation', 'SetCoinDrawable', 'AmbientAnimationRandomize', 'TurnGotoDialogOff', 'SetCompletionDialog', 'SetMissionResetPlayerOutCar', 'SetMissionStartCameraName', 'SetMissionStartMulticontName', 'SetInitialWalk', 'SetDialoguePositions', 'ActivateVehicle', 'SetStageMusicAlwaysOn', 'SetNumValidFailureHints', 'SetVehicleAIParams', 'StageStartMusicEvent', 'AllowMissionAbort', 'MustActionTrigger', 'SetStageAITargetCatchupParams', 'SetFollowDistances', 'SetFadeOut', 'StayInBlack', 'AddStageCharacter', 'SetDurationTime', 'SetFMVInfo', 'SetForcedCar', 'SwapInDefaultCar', 'SetSwapDefaultCarLocator', 'SetSwapForcedCarLocator', 'SetSwapPlayerLocator', 'StreetRacePropsLoad', 'StreetRacePropsUnload', 'SetStageAIRaceCatchupParams', 'DisableHitAndRun', 'NoTrafficForStage', 'SetConditionPosition', 'AddSafeZone', 'AddGagBinding', 'SetPostLevelFMV', 'SetHitNRun', 'SetObjDistance', 'SetMusicState', 'SetIrisWipe', 'RemoveDriver', 'RemoveNPC', 'AddDriver', 'SetCharacterToHide', 'SetLevelOver', 'GagCheckCollCards', 'GagCheckMovie', 'GagSetSoundLoadDistances', 'BindCollectibleTo', 'AddShield', 'SetStatepropShadow', 'AddFlyingActorByLocator', 'AddCollectibleStateProp', 'SetPickupTarget', 'SetObjTargetBoss', 'AllowRockOut', 'ShowHUD', 'SetGameOver', 'GoToPsScreenWhenDone', 'SetMass', 'SetGasScale', 'SetSlipGasScale', 'SetBrakeScale', 'SetTopSpeedKmh', 'SetMaxWheelTurnAngle', 'SetHighSpeedSteeringDrop', 'SetTireGrip', 'SetNormalSteering', 'SetSlipSteering', 'SetEBrakeEffect', 'SetSlipSteeringNoEBrake', 'SetSlipEffectNoEBrake', 'SetCMOffsetX', 'SetCMOffsetY', 'SetCMOffsetZ', 'SetSuspensionLimit', 'SetSpringK', 'SetDamperC', 'SetSuspensionYOffset', 'SetHitPoints', 'SetBurnoutRange', 'SetMaxSpeedBurstTime', 'SetDonutTorque', 'SetWeebleOffset', 'SetWheelieRange', 'SetWheelieOffsetY', 'SetWheelieOffsetZ', 'SetShadowAdjustments', 'SetCharactersVisible', 'SetIrisTransition', 'SetCharacterScale', 'SetGamblingOdds', 'SetDriver', 'SetHasDoors', 'SetShininess', 'SetHighRoof', 'SetHighSpeedGasScale', 'SetGasScaleSpeedThreshold', 'SetAllowSeatSlide', 'ClearVehicleSelectInfo', 'AddFlyingActor', 'SetCollisionAttributes', 'AddSpawnPoint', 'GagSetWeight', 'GagSetLoadDistances', 'SetTotalWasps', 'AddGlobalProp', 'EnableHitAndRun', 'SetHitAndRunMeter', 'SetChaseSpawnRate', 'KillAllChaseAI', 'ResetHitAndRun', 'SetHitAndRunDecayInterior', 'SetMissionNameIndex', 'AddBonusObjective', 'AttachStatePropCollectible', 'MoveStageVehicle', 'SetStageCamera', 'SetBonusMissionStart', 'PlacePlayerAtLocatorName', 'msPlacePlayerCarAtLocatorName', 'ClearTrafficForStage', 'SetStageAIEvadeCatchupParams', 'AllowUserDump', 'SetVehicleToLoad', 'SetConversationCamName', 'SetConversationCamPcName', 'SetConversationCamNpcName', 'SetConversationCamDistance', 'CharacterIsChild', 'SetCarStartCamera', 'SetPlayerCarName', 'SetRespawnRate', 'ActivateTrigger', 'DeactivateTrigger', 'CreateAnimPhysObject', 'CreateActionEventTrigger', 'LinkActionToObjectJoint', 'LinkActionToObject', 'SetCharacterPosition', 'ResetCharacter']

# Engine features: key -> (name, plan stage, PSP difficulty, note)
# Plan stages (CLAUDE.md): 2 collision, 3 driving physics, 4 Homer on foot + skeletal anim, 5 traffic/peds,
# 6 sound, 7 widescreen HUD/menus, 8 missions L1, 9 textures, 10 levels 2-7.
FEATURES = {
 'flow':      ('Каркас миссий: этапы, цели, провал, чекпоинт, прогресс', '8', 'лёгкая', 'этот поток (viewer/mission)'),
 'text':      ('Тексты заданий и названия миссий (текстовая библия srr2.p3d)', '7', 'лёгкая', 'компилятор кладёт готовый UTF-8'),
 'hud':       ('HUD: иконка задания, таймер, счётчик, отсчёт 3-2-1, «этап пройден»', '7', 'средняя', 'ресурсы Scrooby + msnicons/*.p3d'),
 'nav':       ('Маркер цели: сфера carsphere/triggersphere, стрелка, радар', '7', 'средняя', 'модели сфер в missgen.p3d'),
 'load':      ('Подгрузка ресурсов миссии (p3d → PSP-паки), зоны DynaLoad', '8', 'тяжёлая', 'память: ~52 МБ, нужен конвертер пропов/машин/персонажей'),
 'player':    ('Размещение игрока и машины, посадка/высадка, смена машины', '4', 'средняя', ''),
 'car_ai':    ('Машины миссии с ИИ: гонка, погоня, цель, уход, путь по точкам', '5', 'тяжёлая', 'ИИ по точкам + догонялка (catch-up)'),
 'car_phys':  ('Параметры машин (.con), характеристики', '3', 'средняя', ''),
 'npc':       ('Персонажи миссии: появление, ходьба по точкам, разговор по кнопке', '4', 'тяжёлая', 'скиннинг GE до 8 костей/вызов, память на модели'),
 'dialogue':  ('Диалоги: реплики conversations/*.rsd + жесты + камеры', '6', 'средняя', 'звук RSD (PS2 VAG/ADPCM) → PSP'),
 'camera':    ('Анимированные камеры: вступления миссий, камеры диалогов', '8', 'средняя', 'камеры+мультиконтроллеры из p3d'),
 'fmv':       ('Ролики FMV (.rmv = PS2 IPU + RSD)', '8+', 'тяжёлая', 'перекодировать офлайн (PMF/AVC через sceMpeg)'),
 'props':     ('Предметы миссии: collectibles, state props, эффекты подбора', '8', 'средняя', ''),
 'traffic':   ('Трафик: лимит машин, группы моделей', '5', 'средняя', ''),
 'peds':      ('Пешеходы: группы моделей', '5', 'средняя', ''),
 'police':    ('Hit & Run: полиция, шкала, зоны без погони', '5/8', 'средняя', ''),
 'music':     ('Музыка миссий: события и состояния', '6', 'средняя', ''),
 'fx':        ('Затемнения, iris wipe, частицы, тени', '7', 'лёгкая', ''),
 'interiors': ('Интерьеры (Kwik-E-Mart, дом Симпсонов, школа)', '8', 'тяжёлая', 'отдельная геометрия l1i0N.p3d, подмена мира'),
 'gags':      ('Гэги: интерактивные сценки в мире и интерьерах, монеты за них', '8+', 'средняя', '409 гэгов на 7 уровней'),
 'shop':      ('Покупка машин и костюмов, награды за миссии', '8', 'средняя', 'rewards.mfk'),
 'collect':   ('Монеты, карточки, осы-камеры (beecamera)', '8+', 'средняя', 'осы = летающие актёры с ИИ'),
 'level':     ('Прочее уровня: телепорты (отладка), выбор машины в будке, туториал Барта', '8', 'лёгкая', ''),
 'demo':      ('Демо-режим (attract loop)', '-', 'не нужна', 'можно пропустить'),
 'endgame':   ('Конец уровня и игры, финальные ролики', '10', 'лёгкая', ''),
}

class Spec:
    __slots__ = ('name','op','feature','route','when','replay','locs','ru','used')
    def __init__(self, name, feature, route='eng', when='start', replay=False, locs=(), ru=''):
        self.name=name; self.op=OPCODE_ORDER.index(name)+1; self.feature=feature; self.route=route
        self.when=when; self.replay=replay; self.locs=tuple(locs); self.ru=ru; self.used=True

_S = {}
def C(name, feature, route='eng', when='start', replay=False, locs=(), ru=''):
    _S[name] = Spec(name, feature, route, when, replay, locs, ru)

# ---- structure / flow (runtime) ----
C('AddMission','flow','rt',ru='Сюжетная миссия уровня (порядок = порядок прохождения)')
C('AddBonusMission','flow','rt',ru='Необязательная миссия: уличные гонки sr1-3, гонка на ставку gr1, бонус bm1, кино ismovie')
C('SelectMission','flow','rt',ru='Начало скрипта миссии; «m1sd» = вступительная часть (дойти до героя и поговорить)')
C('CloseMission','flow','rt',ru='Конец скрипта миссии')
C('AddStage','flow','rt',ru='Начало этапа. Аргументы: число (смысл неизвестен, храним), "final" = последний этап, "locked","car"|"skin",имя = этап требует купить машину/костюм')
C('CloseStage','flow','rt',ru='Конец этапа')
C('AddObjective','flow','rt',ru='Цель этапа: тип (20 видов) + режим стрелки навигации (neither/both/nearest road/intersection) или имя покупки/"gamble"')
C('CloseObjective','flow','rt',ru='Конец описания цели')
C('AddCondition','flow','rt',ru='Условие провала: timeout, outofvehicle, damage, position, race, followdistance, keepbarrel')
C('CloseCondition','flow','rt',ru='Конец условия')
C('RESET_TO_HERE','flow','rt',ru='Чекпоинт: при провале перезапуск с этого этапа')
C('ShowStageComplete','hud','rt',ru='Показать «этап пройден» (звук+надпись) по завершении этапа')
C('SetStageMessageIndex','text','rt',ru='Текст задания: номер строки MISSION_OBJECTIVE_NN в текстовой библии')
C('SetHUDIcon','hud','rt',ru='Иконка задания в HUD (art/frontend/dynaload/images/msnicons/*)')
C('SetStageTime','hud','rt',ru='Таймер этапа, секунды (заново)')
C('AddStageTime','hud','rt',ru='Добавить секунды к таймеру, оставшемуся с прошлого этапа')
C('UseElapsedTime','hud','rt',ru='Таймер идёт вверх (гонка на ставку: уложиться в пар-время)')
C('SetParTime','hud','rt',ru='Пар-время гонки на ставку, секунды')
C('StartCountdown','hud','rt',ru='Отсчёт перед стартом (имя анимации/звука)')
C('AddToCountdownSequence','hud','rt',ru='Шаг отсчёта: текст ("3","2","PSYCHE","GO"), длительность мс')
C('SetNumValidFailureHints','text','rt',ru='Сколько подсказок показывать при провале')
C('AllowMissionAbort','flow','rt',ru='Запретить выход из миссии через паузу ("false")')
C('SetMissionNameIndex','text','rt',ru='Номер названия миссии (не встречается)')
# ---- objective parameters (runtime) ----
C('SetDestination','nav','rt',locs=(0,),ru='Цель goto/interior/gooutside: локатор (или имя интерьера) + модель маркера (carsphere, triggersphere, иконка-предмет)')
C('SetCollectibleEffect','props','rt',ru='Эффект при подборе/достижении цели (wrench_collect, bonestorm_explosion)')
C('TurnGotoDialogOff','dialogue','rt',ru='Не говорить реплику при прибытии')
C('MustActionTrigger','nav','rt',ru='На точке нужно нажать кнопку действия')
C('SetObjTargetVehicle','flow','rt',ru='Машина-цель (getin/destroy/follow/losetail/dump); "current" = своя машина')
C('SetObjTargetBoss','flow','rt',ru='Цель-босс (НЛО в уровне 7)')
C('SetPickupTarget','flow','rt',ru='Предмет, который надо подобрать машиной (бочка)')
C('AddCollectibleStateProp','props','both',replay=True,locs=(1,),ru='Предмет-стейтпроп (бочка с отходами) на локаторе')
C('SetTalkToTarget','npc','rt',ru='С кем говорить: имя, тип иконки, высота иконки, радиус зоны разговора')
C('SetDialogueInfo','dialogue','rt',ru='Диалог: персонаж 1, персонаж 2, имя разговора (файлы conversations/c_<имя>_*), флаг')
C('SetDialoguePositions','dialogue','both',locs=(0,1,2),ru='Где стоят игрок и NPC во время диалога и где машина; 4-й аргумент = флаг')
C('SetCamBestSide','camera','eng',locs=(0,),ru='Локатор «лучшей стороны» для камеры диалога (2-й арг = миссия, в leveli)')
C('SetConversationCam','camera','eng',ru='Камера на реплику диалога: номер реплики, имя камеры (npc_far, pc_near ...)')
C('AmbientAnimationRandomize','dialogue','eng',ru='Жесты в диалоге случайные или по порядку (кто: 0=игрок 1=NPC)')
C('AddAmbientNpcAnimation','dialogue','eng',ru='Жест NPC на очередную реплику')
C('AddAmbientPcAnimation','dialogue','eng',ru='Жест игрока на очередную реплику')
C('ClearAmbientAnimations','dialogue','eng',ru='Сбросить список жестов (для бонус-миссии из leveli)')
C('SetPresentationBitmap','hud','eng',ru='Картинка-заставка миссии (экран загрузки/пауза)')
C('SetFMVInfo','fmv','rt',ru='Ролик для цели fmv (+ "stopmusic")')
C('SetDurationTime','flow','rt',ru='Длительность цели timer, секунды')
C('SetRaceLaps','flow','rt',ru='Число кругов гонки')
C('AddCollectible','props','rt',locs=(0,),ru='Точка/предмет цели: локатор, модель, реплика при подборе, говорящий')
C('BindCollectibleTo','props','rt',ru='Предмет N выпадает из цели, когда она проходит точку пути M')
C('SetObjDistance','flow','rt',ru='Дистанция для follow/losetail, м')
C('SetCoinFee','shop','rt',ru='Сколько монет заплатить (цель coins)')
C('SetRaceEnteryFee','shop','rt',ru='Ставка в гонке на ставку (выигрыш = ставка x2)')
C('AddObjectiveNPCWaypoint','npc','both',locs=(1,),ru='Точка маршрута NPC на время цели')
C('AddNPC','npc','both',replay=True,locs=(1,),ru='Поставить персонажа миссии на локатор (3-й арг = интерьер)')
C('RemoveNPC','npc','eng',replay=True,ru='Убрать персонажа')
C('AddStageCharacter','player','eng',locs=(1,4),ru='Поставить персонажа (игрока) и машину на локаторы (постановка сцены)')
C('SetCharacterToHide','npc','eng',replay=True,ru='Спрятать персонажа')
C('SetCompletionDialog','dialogue','rt',when='end',ru='Реплика по завершении этапа (имя разговора, персонаж)')
# ---- conditions (runtime) ----
C('SetCondTime','flow','rt',ru='Условие outofvehicle: сколько мс можно быть без машины')
C('SetCondMinHealth','flow','rt',ru='Условие damage: порог здоровья машины')
C('SetCondTargetVehicle','flow','rt',ru='Машина, к которой относится условие ("current" = своя)')
C('SetFollowDistances','flow','rt',ru='Условие followdistance: мин/макс дистанция до цели, м')
C('SetConditionPosition','flow','rt',ru='Условие position: проигрыш, если N соперников финишировали раньше')
# ---- mission setup: player, cars, AI ----
C('SetMissionResetPlayerInCar','player','eng',locs=(0,),ru='Старт/рестарт миссии: игрок в машине на локаторе')
C('SetMissionResetPlayerOutCar','player','eng',locs=(0,1),ru='Старт/рестарт миссии: игрок пешком на локаторе, машина на втором')
C('SetInitialWalk','player','eng',locs=(0,),ru='В начале миссии игрок сам идёт к локатору')
C('SetDynaLoadData','load','eng',ru='Какие зоны мира подгрузить к старту миссии (l1z1.p3d;l1r1.p3d;...)')
C('UsePedGroup','peds','eng',ru='Какая группа пешеходов активна в миссии')
C('InitLevelPlayerVehicle','player','eng',locs=(1,),ru='Машина игрока: модель, локатор, DEFAULT/OTHER (навязанная машина)')
C('SetForcedCar','player','eng',ru='Миссия идёт на навязанной машине (OTHER из InitLevelPlayerVehicle)')
C('SwapInDefaultCar','player','eng',when='end',replay=True,ru='По завершении этапа вернуть свою машину вместо навязанной')
C('SetSwapDefaultCarLocator','player','eng',when='end',locs=(0,),ru='Куда поставить свою машину при возврате')
C('SetSwapForcedCarLocator','player','eng',when='end',locs=(0,),ru='Куда убрать навязанную машину')
C('SetSwapPlayerLocator','player','eng',when='end',locs=(0,),ru='Куда поставить игрока при смене машины')
C('PlacePlayerCar','player','eng',locs=(1,),ru='Поставить машину ("current") на локатор')
C('PutMFPlayerInCar','player','eng',ru='Посадить игрока в машину (старт гонки)')
C('AddStageVehicle','car_ai','both',replay=True,locs=(1,),ru='Машина миссии: модель, локатор, ИИ (race/chase/evade/target/waypoint/NULL), .con, водитель')
C('ActivateVehicle','car_ai','eng',locs=(1,),ru='Включить ИИ у ранее добавленной машины: имя, локатор/NULL, режим')
C('AddStageWaypoint','car_ai','eng',locs=(0,),ru='Точка пути ИИ-машин этапа (конец пути = «доехал»)')
C('SetVehicleAIParams','car_ai','eng',ru='Параметры ИИ-машины (два целых; смысл: срезы/агрессия, точнее неизвестно)')
C('SetStageAIRaceCatchupParams','car_ai','eng',ru='Догонялка (rubber band) гонщика: дистанция и множители скорости')
C('SetStageAITargetCatchupParams','car_ai','eng',ru='Догонялка машины-цели: мин/макс дистанция')
C('SetStageAIEvadeCatchupParams','car_ai','eng',ru='Догонялка убегающей машины (не встречается)')
C('SuppressDriver','car_ai','eng',ru='Машина без водителя-модели')
C('AddDriver','car_ai','eng',replay=True,ru='Посадить водителя-персонажа в машину')
C('RemoveDriver','car_ai','eng',replay=True,ru='Высадить водителя-персонажа')
C('LoadDisposableCar','load','eng',ru='Загрузить модель машины для миссии/уровня (AI/DEFAULT/OTHER)')
C('SetMaxTraffic','traffic','eng',ru='Максимум машин трафика на этапе')
C('NoTrafficForStage','traffic','eng',ru='Без трафика на этапе')
C('DisableHitAndRun','police','eng',ru='Выключить Hit & Run на этапе')
C('SetHitNRun','police','eng',ru='Hit & Run: сразу полная шкала (полиция гонится) на этапе')
C('AddSafeZone','police','eng',locs=(0,),ru='Зона (локатор, радиус), где полиция не преследует')
C('AddStageMusicChange','music','eng',ru='Сменить музыку на этапе')
C('SetStageMusicAlwaysOn','music','eng',ru='Музыка этапа не выключается')
C('StageStartMusicEvent','music','eng',ru='Музыкальное событие в начале этапа (M3_drama, M4_start...)')
C('SetMusicState','music','eng',ru='Состояние интерактивной музыки (Mission4, Stage1)')
C('SetFadeOut','fx','eng',when='end',ru='Затемнить экран по завершении этапа, секунды')
C('StayInBlack','fx','eng',ru='Экран остаётся чёрным на этапе (постановка между сценами)')
C('SetIrisWipe','fx','eng',when='end',ru='Переход «ирисовой диафрагмой» по завершении этапа')
C('SetMissionStartCameraName','camera','eng',ru='Камера вступления миссии (имя камеры в p3d)')
C('SetMissionStartMulticontName','camera','eng',ru='Анимация (multicontroller) камеры вступления')
C('SetAnimatedCameraName','camera','eng',ru='Анимированная камера миссии (имя)')
C('SetAnimCamMulticontName','camera','eng',ru='Анимация анимированной камеры')
C('StreetRacePropsLoad','load','eng',ru='Подгрузить пропы гонки (конусы, двери) при старте')
C('StreetRacePropsUnload','load','eng',ru='Выгрузить пропы гонки по окончании')
C('SetLevelOver','endgame','rt',ru='После этой миссии уровень пройден (переходная миссия)')
C('SetGameOver','endgame','rt',ru='После этой миссии игра пройдена')
C('GoToPsScreenWhenDone','endgame','eng',ru='После миссии перейти на экран паузы/итогов')
C('SetPostLevelFMV','fmv','eng',ru='Ролик после уровня')
C('ShowHUD','hud','eng',ru='Показать/скрыть HUD')
C('AllowRockOut','fx','eng',ru='Разрешить «кайфовать» под музыку в машине (анимация)')
C('SetDemoLoopTime','demo','eng',ru='Длительность демо-петли, мс')
# ---- loading ----
C('LoadP3DFile','load','eng',ru='Загрузить p3d (модели, локаторы, камеры, иконки); 2-й арг = куча памяти')
# ---- level init (leveli.mfk) ----
C('EnableTutorialMode','level','eng',ru='Подсказки Барта (туториал) вкл/выкл')
C('AddCharacter','player','eng',ru='Игровой персонаж уровня (homer, bart ...) и его модель')
C('CreateChaseManager','police','eng',ru='Полиция: машина, .con, число машин')
C('SetHitAndRunDecay','police','eng',ru='Скорость спада шкалы Hit & Run')
C('SetNumChaseCars','police','eng',ru='Сколько полицейских машин в погоне')
C('AddNPCCharacterBonusMission','npc','both',locs=(2,),ru='Персонаж, дающий бонус-миссию: имя, модель, локатор, миссия, иконка, разговор, флаг, тень иконки')
C('AddBonusMissionNPCWaypoint','npc','eng',locs=(1,),ru='Маршрут персонажа бонус-миссии')
C('SetBonusMissionDialoguePos','dialogue','eng',locs=(1,2,3),ru='Позиции диалога бонус-миссии: миссия, игрок, NPC, машина')
C('AddAmbientCharacter','npc','both',locs=(1,),ru='Фоновый персонаж, с которым можно поговорить: имя, локатор, радиус')
C('AddAmbientNPCWaypoint','npc','eng',locs=(1,),ru='Маршрут фонового персонажа')
C('AddPurchaseCarReward','shop','both',locs=(3,5),ru='Продавец машин: магазин, продавец, модель, локатор, радиус, локатор машины')
C('AddPurchaseCarNPCWaypoint','shop','eng',locs=(1,),ru='Маршрут продавца машин')
C('CreateTrafficGroup','traffic','eng',ru='Начало группы машин трафика')
C('AddTrafficModel','traffic','eng',ru='Модель трафика: имя, число, флаг (припаркованные?)')
C('CloseTrafficGroup','traffic','eng',ru='Конец группы трафика')
C('CreatePedGroup','peds','eng',ru='Начало группы пешеходов N')
C('AddPed','peds','eng',ru='Модель пешехода: имя, число')
C('ClosePedGroup','peds','eng',ru='Конец группы пешеходов')
C('SetCoinDrawable','collect','eng',ru='Модель монеты')
C('SetParticleTexture','fx','eng',ru='Текстура частиц N')
C('PreallocateActors','collect','eng',ru='Заранее создать N актёров (осы-камеры)')
C('SetProjectileStats','collect','eng',ru='Снаряды ос: имя, скорость, урон')
C('SetActorRotationSpeed','collect','eng',ru='Скорость поворота актёров (ос)')
C('AddSpawnPointByLocatorScript','collect','eng',locs=(3,),ru='Точка появления осы: имя, тип, поведение, локатор, радиусы')
C('AddBehaviour','collect','eng',ru='Поведение актёра (ATTRACTION, ATTACK_PLAYER ...) с параметрами')
C('AddShield','collect','eng',ru='Щит у актёра (оса-камера)')
C('AddFlyingActorByLocator','collect','eng',locs=(2,),ru='Летающий актёр на локаторе (корабль Planet Express, НЛО)')
C('SetStatepropShadow','fx','eng',ru='Тень-световое пятно для стейтпропа (фонари)')
C('AddVehicleSelectInfo','level','eng',ru='Машина в телефонной будке: p3d, имя, водитель')
C('AddTeleportDest','level','eng',ru='Точка телепорта (отладочное меню): имя, x y z, зоны')
C('SetTotalGags','gags','eng',ru='Сколько гэгов на уровне (статистика)')
C('BindReward','shop','eng',ru='Награда: имя, p3d, car/skin, как получить (defaultcar/bonusmission/streetrace/forsale), уровень, цена, продавец')
C('SetCarAttributes','shop','eng',ru='Характеристики машины для меню (скорость, разгон, управление, прочность)')
# ---- gags (level.mfk) ----
C('ClearGagBindings','gags','eng',ru='Сбросить список гэгов')
C('GagBegin','gags','eng',ru='Начало гэга: p3d со сценкой')
C('GagSetInterior','gags','eng',ru='Гэг в интерьере N')
C('GagSetCycle','gags','eng',ru='Режим проигрывания: cycle/single/reset')
C('GagSetPosition','gags','eng',ru='Где стоит гэг: x y z или локатор')
C('GagSetRandom','gags','eng',ru='Случайный выбор гэга')
C('GagSetSound','gags','eng',ru='Звук гэга')
C('GagSetTrigger','gags','eng',ru='Как запускается: "touch"/"action", позиция x y z, радиус (или локатор, радиус)')
C('GagEnd','gags','eng',ru='Конец гэга')
C('GagSetSparkle','gags','eng',ru='Блёстки над гэгом')
C('GagSetPersist','gags','eng',ru='Гэг остаётся после срабатывания')
C('GagSetCoins','gags','eng',ru='Монеты за гэг: число, разброс')
C('GagSetAnimCollision','gags','eng',ru='Коллизия у анимированного гэга')
C('GagSetIntro','gags','eng',ru='Кадр/флаг вступления гэга')
C('GagSetOutro','gags','eng',ru='Кадр/флаг окончания гэга')
C('GagSetCameraShake','gags','eng',ru='Тряска камеры: сила, задержка мс, длительность')
C('GagPlayFMV','fmv','eng',ru='Гэг запускает ролик')
C('GagCheckCollCards','gags','eng',ru='Гэг-проверка «собраны все карточки» (диалог-награда)')
C('GagCheckMovie','gags','eng',ru='Гэг-кинотеатр: ролик по условию')
C('GagSetSoundLoadDistances','gags','eng',ru='Дистанции подгрузки звука гэга')
C('AddGagBinding','gags','eng',ru='Привязка гэга к интерьеру: интерьер, p3d, режим, вес, звук')

# ---- donut-registered commands that never appear in the disc's .mfk (mostly car .con tuning) ----
_CON = ['SetMass','SetGasScale','SetSlipGasScale','SetBrakeScale','SetTopSpeedKmh','SetMaxWheelTurnAngle','SetHighSpeedSteeringDrop','SetTireGrip','SetNormalSteering','SetSlipSteering','SetEBrakeEffect','SetSlipSteeringNoEBrake','SetSlipEffectNoEBrake','SetCMOffsetX','SetCMOffsetY','SetCMOffsetZ','SetSuspensionLimit','SetSpringK','SetDamperC','SetSuspensionYOffset','SetHitPoints','SetBurnoutRange','SetMaxSpeedBurstTime','SetDonutTorque','SetWeebleOffset','SetWheelieRange','SetWheelieOffsetY','SetWheelieOffsetZ','SetShadowAdjustments','SetCharactersVisible','SetIrisTransition','SetCharacterScale','SetGamblingOdds','SetDriver','SetHasDoors','SetShininess','SetHighRoof','SetHighSpeedGasScale','SetGasScaleSpeedThreshold','SetAllowSeatSlide']
for _n in _CON:
    if _n not in _S: C(_n,'car_phys','eng',ru='Тюнинг машины (файлы scripts/cars/*.con), не в .mfk')
_OTHER = {
 'HelloWorld':('level','Отладочная команда'),'ClearVehicleSelectInfo':('level','Очистить список машин будки'),
 'AddFlyingActor':('collect','Летающий актёр (без локатора)'),'SetCollisionAttributes':('props','Атрибуты коллизии объекта'),
 'AddSpawnPoint':('collect','Точка появления актёра'),'GagSetWeight':('gags','Вес гэга'),'GagSetLoadDistances':('gags','Дистанции подгрузки гэга'),
 'SetTotalWasps':('collect','Сколько ос на уровне'),'AddGlobalProp':('props','Глобальный проп'),'EnableHitAndRun':('police','Включить Hit & Run'),
 'SetHitAndRunMeter':('police','Задать шкалу Hit & Run'),'SetChaseSpawnRate':('police','Частота появления полиции'),'KillAllChaseAI':('police','Убрать полицию'),
 'ResetHitAndRun':('police','Сбросить Hit & Run'),'SetHitAndRunDecayInterior':('police','Спад шкалы в интерьере'),
 'AddBonusObjective':('flow','Дополнительная цель'),'AttachStatePropCollectible':('props','Прикрепить стейтпроп-предмет'),
 'MoveStageVehicle':('car_ai','Переставить машину миссии'),'SetStageCamera':('camera','Камера этапа'),'SetBonusMissionStart':('flow','Старт бонус-миссии'),
 'PlacePlayerAtLocatorName':('player','Поставить игрока на локатор'),'msPlacePlayerCarAtLocatorName':('player','Поставить машину игрока на локатор'),
 'ClearTrafficForStage':('traffic','Убрать трафик на этапе'),'AllowUserDump':('flow','Разрешить сброс груза'),'SetVehicleToLoad':('load','Машина к загрузке'),
 'SetConversationCamName':('camera','Камера диалога'),'SetConversationCamPcName':('camera','Камера диалога на игрока'),'SetConversationCamNpcName':('camera','Камера диалога на NPC'),
 'SetConversationCamDistance':('camera','Дистанция камеры диалога'),'CharacterIsChild':('npc','Персонаж-ребёнок (рост)'),'SetCarStartCamera':('camera','Камера старта в машине'),
 'SetPlayerCarName':('player','Имя машины игрока'),'SetRespawnRate':('collect','Частота возрождения'),'ActivateTrigger':('flow','Включить триггер'),'DeactivateTrigger':('flow','Выключить триггер'),
 'CreateAnimPhysObject':('props','Анимированный физобъект'),'CreateActionEventTrigger':('props','Триггер действия'),'LinkActionToObjectJoint':('props','Действие к суставу объекта'),
 'LinkActionToObject':('props','Действие к объекту'),'SetCharacterPosition':('player','Поставить персонажа'),'ResetCharacter':('player','Персонажа на локатор'),
}
for _n,(_f,_r) in _OTHER.items():
    if _n not in _S: C(_n,_f,'eng',ru=_r+' (не встречается в скриптах диска)')

missing = [n for n in OPCODE_ORDER if n not in _S]
assert not missing, missing
SPECS = [_S[n] for n in OPCODE_ORDER]
BY_NAME = {s.name.lower(): s for s in SPECS}

# argument signature from donut cmd.json (min args, typed variants)
def load_signatures(root):
    path = Path(root) / 'donut/dev/codegen/cmd.json'
    data = json.loads(path.read_text())
    sig = {}
    for name, v in data.items():
        sig[name] = (v.get('min', 0), v.get('types', [[]]))
    return sig

OBJECTIVES = ['goto','getin','talkto','dialogue','interior','gooutside','race','follow','losetail','delivery','dump',
              'destroy','pickupitem','destroyboss','timer','fmv','buycar','buyskin','coins','dummy']
CONDITIONS = ['timeout','outofvehicle','damage','position','race','followdistance','keepbarrel']

OBJ_RU = {
 'goto':'доехать/дойти до точки','getin':'сесть в машину','talkto':'подойти и поговорить с персонажем (кнопка)',
 'dialogue':'диалог (сценка)','interior':'войти в здание','gooutside':'выйти из здания',
 'race':'гонка по контрольным точкам (с соперниками или на время)','follow':'следовать за машиной, не отставая',
 'losetail':'оторваться от погони','delivery':'собрать предметы (в любом порядке)','dump':'таранить машину, собирать выпадающее',
 'destroy':'разбить машину-цель','pickupitem':'подобрать предмет машиной','destroyboss':'поразить босса',
 'timer':'пауза/постановка на N секунд','fmv':'ролик','buycar':'купить машину','buyskin':'купить костюм',
 'coins':'заплатить монеты (ставка)','dummy':'пустышка (демо E3)'}
COND_RU = {
 'timeout':'время вышло','outofvehicle':'слишком долго без машины','damage':'машина разбита',
 'position':'соперники финишировали раньше','race':'цель доехала до конца пути раньше',
 'followdistance':'слишком отстал от цели','keepbarrel':'потерян груз (бочка)'}
