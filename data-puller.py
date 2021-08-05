#!/usr/bin/env python3
from itertools import count
from pathlib import Path
from plumbum import cli
from urllib import parse

import json
import requests


class DataPuller(cli.Application):
    API_URL = "https://quake-stats.bethesda.net/api/v2"
    LEADERBOARD_PAGE_SIZE = 100
    MIN_INTERESTING_RATING = 1825

    def make_api_call(self, call, params):
        url = "{}/{}".format(self.API_URL, call)
        response = requests.get(url, params=params)
        print("request:", response.url, response.status_code, flush=True)
        assert response.status_code == 200
        return json.loads(response.text)

    def main(self):
        for offset in count(0, self.LEADERBOARD_PAGE_SIZE):
            leaderboard = self.make_api_call("Leaderboard", {"from": offset, "board": "duel", "season": "current"})
            assert leaderboard["boardType"] == "duel"
            entries = leaderboard["entries"]
            if len(entries) == 0:
                break
            assert len(entries) <= self.LEADERBOARD_PAGE_SIZE
            if max([entry["eloRating"] for entry in entries]) < self.MIN_INTERESTING_RATING:
                break
            for entry in entries:
                username = entry["userName"]
                statistics = self.make_api_call("Player/Stats", {"name": username})
                assert statistics["name"] == username
                for match in statistics["matches"]:
                    match_statistics = self.make_api_call("Player/Games", {"id": match["id"]})
                    if match_statistics is None:
                        continue
                    assert match_statistics["id"] == match["id"]
                    if match_statistics["gameMode"] != "GameModeClassicDuel":
                        continue
                    reports = match_statistics["battleReportPersonalStatistics"]
                    players = [report["nickname"] for report in reports]
                    if len(players) != 2:
                        continue
                    scores = [report["score"] for report in reports]
                    if max(scores) == match_statistics["scoreLimit"]:
                        continue
                    match_description = {
                        "id": match_statistics["id"],
                        "time_limit": match_statistics["timeLimit"],
                        "timestamp": match_statistics["playedDateTime"],
                        "players": players
                    }
                    print(json.dumps(match_description), flush=True)


if __name__ == "__main__":
    DataPuller.run()
