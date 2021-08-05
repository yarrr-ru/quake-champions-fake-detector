#!/usr/bin/env python3
from itertools import count
from pathlib import Path
from plumbum import cli
from urllib import parse

import json
import requests


class DataPuller(cli.Application):
    API_URL = "https://quake-stats.bethesda.net/api/v2"
    LEADERBOARD_PAGE_SIZE = 20

    def make_api_call(self, call, params):
        url = "{}/{}".format(self.API_URL, call)
        response = requests.get(url, params=params)
        assert response.status_code == 200
        return json.loads(response.text)

    def main(self):
        for offset in count(0, self.LEADERBOARD_PAGE_SIZE):
            leaderboard = self.make_api_call("Leaderboard", {"from": offset, "board": "duel", "season": "current"})
            assert leaderboard["boardType"] == "duel"
            for entry in leaderboard["entries"]:
                username = entry["userName"]
                statistics = self.make_api_call("Player/Stats", {"name": username})
                assert statistics["name"] == username
                for match in statistics["matches"]:
                    match_statistics = self.make_api_call("Player/Games", {"id": match["id"]})
                    assert match_statistics["id"] == match["id"]
                    if match_statistics["gameMode"] != "GameModeClassicDuel":
                        continue
                    players = [report["nickname"] for report in match_statistics["battleReportPersonalStatistics"]]
                    if len(players) != 2:
                        continue
                    match_description = {
                        "id": match_statistics["id"],
                        "time_limit": match_statistics["timeLimit"],
                        "timestamp": match_statistics["playedDateTime"],
                        "players": players
                    }
                    print(json.dumps(match_description))


if __name__ == "__main__":
    DataPuller.run()
