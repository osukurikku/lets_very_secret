from typing import Callable, Dict, List, TYPE_CHECKING, Set
from objects import glob
import time
import traceback

from common.constants.gameModes import getGameModeForDB

if TYPE_CHECKING:
    from objects import score
    from objects import beatmap

class Achievement:
    """A class to represent a single osu! achievement."""
    __slots__ = ('id', 'file', 'name',
                 'desc', 'cond', 'mode')

    def __init__(self, id: int, file: str, name: str,
                 desc: str, cond: Callable, mode: int) -> None:
        self.id = id
        self.file = file
        self.name = name
        self.desc = desc

        self.cond = cond
        self.mode = mode

    def __repr__(self) -> str:
        return f'{self.file}+{self.name}+{self.desc}'

class AchievementStorage:

    achievements: Dict[int, List[Achievement]] = {
        0: [],
        1: [],
        2: [],
        3: [],
        4: []
    }  # 4 - is special type of achievements, that's available in any mode, and can be recieved only once!

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(AchievementStorage, cls).__new__(cls)
        return cls.instance
    
    @classmethod
    def ckattempts(cls, score: 'score', need_count: int):
        countDB = glob.db.fetch(
            "SELECT COUNT(1) as count FROM scores WHERE scores.beatmap_md5 = %s AND scores.userid = %s",
            [score.fileMd5, score.playerUserID]
        )

        if countDB['count'] != need_count:
            return False

        return True


    @classmethod
    def ckpack(cls, score: 'score', beatmap_ids: List[int]) -> bool:
        countDB = glob.db.fetch(
            "SELECT COUNT(1) as count FROM scores INNER JOIN beatmaps on beatmaps.beatmap_md5 = scores.beatmap_md5 WHERE scores.completed = 3 AND scores.userid = %s AND beatmaps.beatmap_id IN ({seq})".format(
                seq=', '.join(['%s'] * len(beatmap_ids))
            ),
            [score.playerUserID, *beatmap_ids]
        )

        if countDB['count'] != len(beatmap_ids):
            return False

        return True

    @classmethod
    def load_achievements(cls) -> bool:
        db_data = glob.db.fetchAll("SELECT * FROM achievements")

        for row in db_data:
            try:
                condition = eval(f"lambda score, bmap, user_data: {row.pop('cond')}")
            except Exception as e:
                traceback.print_exc()
                continue
            achievement = Achievement(**row, cond=condition)

            cls.achievements[row['mode']].append(achievement)

        return True

    @classmethod
    def unlock_achievements(cls, sc: 'score', bm: 'beatmap', newUserData: dict) -> Set[Achievement]:
        db_data = glob.db.fetchAll(
            'SELECT ua.achievement_id id FROM users_achievements ua '
            'LEFT JOIN achievements a ON a.id = ua.achievement_id '
            'WHERE ua.user_id = %s AND (a.mode = %s OR a.mode = 4)',
            [sc.playerUserID, sc.gameMode]
        )
        user_achievements = [row['id'] for row in db_data]
        receieved_achs = set()

        for ach in (*cls.achievements[sc.gameMode], *cls.achievements[4]):
            if ach.id in user_achievements:
                continue  # user received this achievement earlier, ignore it

            if ach.cond(sc, bm, newUserData):
                # user passed condition, insert into him achievements!
                glob.db.execute(
                    'INSERT INTO users_achievements '
                    '(user_id, achievement_id, time) '
                    'VALUES (%s, %s, %s)',
                    [sc.playerUserID, ach.id, int(time.time())]
                )
                receieved_achs.add(ach)

        return receieved_achs
