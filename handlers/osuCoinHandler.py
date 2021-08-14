import tornado.gen
import tornado.web

from common.ripple import userUtils
from common.web import requestsManager
from secret.discord_hooks import Webhook
from constants import rankedStatuses
from objects import beatmap
from objects import glob

from helpers import kotrikhelper
import hashlib


MODULE_NAME = "osuCoinHandler"
class handler(requestsManager.asyncRequestHandler):
    """
    Handler for /web/coins.php
    
    First april joke in 2015, which osu!code contains today...
    """
    @tornado.web.asynchronous
    @tornado.gen.engine
    def asyncGet(self):
        ip = self.getRequestIP()
        if not requestsManager.checkArguments(self.request.arguments, ["u", "h", "action", "cs", "c"]):
            return self.write("error: gimme more arguments")

        username = self.get_argument("u")
        password = self.get_argument("h")
        action = self.get_argument("action")
        userCoins = int(self.get_argument("c"))
        checksum = self.get_argument("cs")

        userID = userUtils.getID(username)
        if userID == 0:
            return self.write("error: pass1")
        if not userUtils.checkLogin(userID, password):
            return self.write("error: pass2")        
      
        if glob.redis.get(f"kurikku:coins_cd:{userID}") is not None:
            return self.write(str(userCoins))
        glob.redis.set(f"kurikku:coins_cd:{userID}", 1, 1)

        actualCoins = glob.redis.get(f"kurikku:coins:{userID}")
        if not actualCoins:
            glob.redis.set(f"kurikku:coins:{userID}", 1)
            actualCoins = b"1"
            return self.write("1")
        actualCoins = int(actualCoins.decode())
        
        actualBeatmap = glob.redis.get(f"kurikku:current_map:{userID}")
        if not actualBeatmap:
            return self.write(str(userCoins))
         
        beatmapInfo = beatmap.beatmap()
        beatmapInfo.setDataFromDB(actualBeatmap.decode())
        if beatmapInfo.rankedStatus not in [rankedStatuses.RANKED, rankedStatuses.APPROVED, rankedStatuses.QUALIFIED, rankedStatuses.LOVED]:
            # cancel, because map is unranked
            return self.write(str(userCoins))

        if action == "check":
            return self.write(str(actualCoins))
        elif action == "use":
            actualCoins-=1
            if actualCoins < 0:
                glob.redis.set(f"kurikku:coins:{userID}", 1)
                return self.write("1")

            hashedString = str(hashlib.md5(f"{username}{actualCoins}osuycoins".encode()).hexdigest())
            if hashedString != checksum:
                return self.write(str(actualCoins+1))
        
            glob.redis.set(f"kurikku:coins:{userID}", actualCoins)
        elif action == "recharge":
            # нахуя это надо не понимаю, так что просто делаем вид, что что-то делаем
            # а и я дохуя душный, поэтому я не дам доп коины)00
            pass
        elif action == "earn":
            actualCoins+=1
            hashedString = str(hashlib.md5(f"{username}{actualCoins}osuycoins".encode()).hexdigest())
            if hashedString != checksum:
                return self.write(str(actualCoins-1))
            
            glob.redis.set(f"kurikku:coins:{userID}", actualCoins)

        return self.write(str(actualCoins))
