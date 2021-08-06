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
    ITEM_RESPAWN_COOLDOWN = 30

    def make_api_call(self, call, params):
        url = "{}/{}".format(self.API_URL, call)
        response = requests.get(url, params=params)
        print("request:", response.url, response.status_code, flush=True)
        assert response.status_code == 200
        return json.loads(response.text)

    def major_items_estimation(self, match_statistics):
        reports = match_statistics["battleReportPersonalStatistics"]
        mega = sum(report["megaHealthPickups"] for report in reports)
        heavy = sum(report["heavyArmorPickups"] for report in reports)
        return self.ITEM_RESPAWN_COOLDOWN * (max(mega, heavy) - 1)

    def champions_time_estimation(self, match_statistics):
        reports = match_statistics["battleReportPersonalStatistics"]
        max_champions_time = 0
        for report in reports:
            champions_time = report["championsTime"]
            assert len(champions_time) == 1
            for champions, life_time in champions_time.items():
                max_champions_time = max(life_time, max_champions_time)
        return max_champions_time // 1000

    def should_estimate_time_limit(self, match_statistics):
        reports = match_statistics["battleReportPersonalStatistics"]
        players = [report["nickname"] for report in reports]
        scores = [report["score"] for report in reports]
        score_limit = match_statistics["scoreLimit"]
        return len(players) == 1 or max(scores) == score_limit

    def match_players(self, username, match_statistics):
        reports = match_statistics["battleReportPersonalStatistics"]
        players = [report["nickname"] for report in reports]
        if username not in players:
            players.append(username)
        return players

    def calculate_time_limit(self, match_statistics):
        time_limit = match_statistics["timeLimit"]

        assert self.champions_time_estimation(
            match_statistics) >= self.major_items_estimation(match_statistics)

        if self.should_estimate_time_limit(match_statistics):
            return self.champions_time_estimation(match_statistics)
        else:
            return time_limit

    def main(self):
        for offset in count(0, self.LEADERBOARD_PAGE_SIZE):
            leaderboard = self.make_api_call(
                "Leaderboard", {
                    "from": offset, "board": "duel", "season": "current"})
            assert leaderboard["boardType"] == "duel"
            entries = leaderboard["entries"]
            if len(entries) == 0:
                break
            assert len(entries) <= self.LEADERBOARD_PAGE_SIZE
            if max([entry["eloRating"] for entry in entries]) < self.MIN_INTERESTING_RATING:
                break
            for entry in entries:
                if entry["eloRating"] < self.MIN_INTERESTING_RATING:
                    break
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
                    players = self.match_players(username, match_statistics)
                    if len(players) != 2:
                        continue
                    time_limit = self.calculate_time_limit(match_statistics)
                    match_description = {
                        "id": match_statistics["id"],
                        "time_limit": time_limit,
                        "timestamp": match_statistics["playedDateTime"],
                        "players": players
                    }
                    print(json.dumps(match_description), flush=True)


if __name__ == "__main__":
    DataPuller.run()
