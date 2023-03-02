# %%
import requests
import conf
from abc import abstractmethod
from itertools import islice
import threading
from contextlib import contextmanager
import logging
import traceback
import sys
from typing import Optional

# %%

# Сущность антидетект-браузера https://anty.dolphin.ru.com/
class AntyDolphinScript:
    def __init__(self, auth_token, limit_profiles = None, max_profiles_count: Optional[int] = None):
        # токен - первый входной параметр
        self.auth_token = auth_token
        # список получаемых профилей
        self.profiles = None
        # лимит - количество профилей, обрабатываемых за раз 
        self.limit_profiles = limit_profiles
        # максимальное количество профилей
        self.max_profiles_count = max_profiles_count
        # количество отработавших профилей (в конце всегда будет равно количеству всех профилей)
        self.work_profiles_count = 0
        # количество успешно отработанных профилей
        self.success_profiles_count = 0
        # результаты работы профилей
        self.profile_results = {}
        # Функция обработки потока
        self.target = self.automation

    # получить профили
    def get_profiles(self):
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        response = requests.get("https://anty-api.com/browser_profiles", headers=headers)
        response_json = response.json()
        # print(response_json)
        data = response_json["data"]
        profiles = {}
        if len(data) > 0:
            for profile in data:
                profiles[profile["id"]] = profile["name"]
            self.profiles = profiles
            if self.limit_profiles is None:
                self.limit_profiles = len(self.profiles)
            return
        raise Exception("Profiles not found")

    @abstractmethod
    def getLogger(self, browser_info) -> logging.Logger:
        pass

    @contextmanager
    def automation(self, lock, profile_id, profile_name):
        try:
            logger = None
            browser_info = self.start(profile_id)
            logger = self.getLogger(browser_info)
            logger.info("Profile has been started")
            yield logger
            logger.info("Close the browser")
            self.close(profile_id)
            logger.info("Success")
            lock.acquire()
            self.profile_results[profile_id] = {"successfully": True}
            lock.release()
        except Exception as ex:
            if not logger is None:
                logger.error(traceback.format_exc())
                logger.error(ex)
            else:
                print(traceback.format_exc())
                print(ex)
            self.close(profile_id)
            lock.acquire()
            self.profile_results[profile_id] = {"successfully": False, "error": ex}
            lock.release()

    def start(self, profile_id):
        response = requests.get(
            f"http://localhost:3001/v1.0/browser_profiles/{profile_id}/start?automation=1"
        ).json()
        print(response)
        if "errorObject" in response:
            raise Exception(response["errorObject"]["text"])
        result = {
            "port": response["automation"]["port"],
            "wsEndpoint": response["automation"]["wsEndpoint"]
        }
        return result

    def close(self, profile_id):
        response = requests.get(
            f"http://localhost:3001/v1.0/browser_profiles/{profile_id}/stop"
        ).json()
        if not response["success"]:
            print(response)

    def run_profiles(self):
        if self.profiles is None:
            self.get_profiles()
        max_profiles_count = len(self.profiles) if self.max_profiles_count is None else self.max_profiles_count
        while self.work_profiles_count < max_profiles_count:
            current_profiles = dict(
                islice(
                    self.profiles.items(), self.work_profiles_count, self.work_profiles_count + self.limit_profiles
                )
            )
            print(current_profiles)
            profiles_str = ", ".join(list(current_profiles.values()))
            print(f"Profiles for work: {profiles_str}")
            lock = threading.Lock()
            threads = []
            for profile_id in current_profiles:
                profile_name = current_profiles[profile_id]
                print(f"Start automation for profile: {profile_name}")
                # task = asyncio.create_task(self.automation(lock, profile_id, profile_name))
                # task
                t = threading.Thread(target=self.automation, args=(lock, profile_id, profile_name))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
            self.work_profiles_count += self.limit_profiles

        self.work_profiles_count = max_profiles_count

        # if (profiles_count >= max_profiles_count):
        #     print('All profiles have worked out')
        # else:
        #     print(f"{profiles_count}/{max_profiles_count} profiles have worked out")

        self.success_profiles_count = len(
            list(
                filter(
                    lambda el: el,
                    [
                        profile_result["successfully"]
                        for profile_result in self.profile_results.values()
                    ],
                )
            )
        )

        print(
            f"Successfully completed profiles: {self.success_profiles_count}/{self.work_profiles_count}"
        )
# %%
if '-t' in sys.argv and __name__ == '__main__':
    # %%
    script = AntyDolphinScript(conf.AUTH_TOKEN)
    script.get_profiles()
    script.profiles
    # %%
    script.start(43499381)
    # %%
    script.close(43499381)
    # %%
    script.run_profiles()
    # %%
elif __name__ == '__main__':
    pass