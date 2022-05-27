#    Copyright 2022 Bertrand Madet

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import datetime
import functools
import locale
import os
import jinja2
import requests
import roman


locale.setlocale(locale.LC_ALL, "")


def get_ws_url():
    return "http://192.168.1.128/ws/"


def get_from_ws(path):
    print(f"Looking for {path} in web service !")
    filepath = os.path.join("temp", "-".join(path.split("/")) + ".json")
    r = requests.get(get_ws_url() + path)
    if r.status_code == 200:
        with open(filepath, "w") as file:
            file.write(r.text)
        return r.json()


def get_jinja_env():
    loader = jinja2.FileSystemLoader("templates")
    return jinja2.Environment(loader=loader, autoescape=jinja2.select_autoescape)


def generate_editions(editions, editionsId):
    env = get_jinja_env()
    maintemplate = env.get_template("main.html.jinja")
    gamestemplate = env.get_template("games.html.jinja")
    coachrankingstemplate = env.get_template("rankings-coach.html.jinja")
    squadrankingstemplate = env.get_template("rankings-squad.html.jinja")
    for edition in editions:
        print("Edition id:", edition["id"])

        target = os.path.join("build", "main-" + str(edition["id"]) + ".html")
        with open(target, "w") as file:
            file.write(maintemplate.render(edition=edition, editionsId=editionsId))

        target = os.path.join("build", "games-" + str(edition["id"]) + ".html")
        with open(target, "w") as file:
            file.write(gamestemplate.render(edition=edition, editionsId=editionsId))

        target = os.path.join("build", "rankings-" + str(edition["id"]) + ".html")
        with open(target, "w") as file:
            if edition["squadCompetition"]:
                file.write(
                    squadrankingstemplate.render(edition=edition, editionsId=editionsId)
                )
            else:
                file.write(
                    coachrankingstemplate.render(edition=edition, editionsId=editionsId)
                )


def prepare_edition(edition):
    edition["shortname"] = "RdvBB " + roman.toRoman(edition["id"])
    edition["squadCompetition"] = edition["fullTriplette"]
    edition["name"] = "Rendez-vous Bloodbowl " + roman.toRoman(edition["id"])
    [year, month, day] = map(int, edition["day1"].split("-"))
    edition["day1InFrench"] = datetime.date(year, month, day).strftime("%d %B %Y")
    [year, month, day] = map(int, edition["day2"].split("-"))
    edition["day2InFrench"] = datetime.date(year, month, day).strftime("%d %B %Y")
    return edition


def prepare_editions(editions):
    return [prepare_edition(edition) for edition in editions]


def add_squad_id_to_game(game, coachsById):
    coach1 = coachsById[str(game["teamId1"])]
    coach2 = coachsById[str(game["teamId2"])]
    game["squad1Id"] = coach1["coachTeamId"]
    game["squad1Name"] = coach1["coachTeamName"]
    game["squad2Id"] = coach2["coachTeamId"]
    game["squad2Name"] = coach2["coachTeamName"]
    return game


def reduce_game_to_confrontations(accumulator, game):
    if game["squad1Id"] != accumulator["currentSquadId"]:
        if accumulator["currentSquadId"]:
            accumulator["confrontations"].append(accumulator["currentConfrontation"])
        accumulator["currentSquadId"] = game["squad1Id"]
        accumulator["currentConfrontation"] = {
            "squad1": game["squad1Name"],
            "squad2": game["squad2Name"],
            "games": [],
            "finale": game["finale"],
        }
    if game["finale"]:
        accumulator["currentConfrontation"]["finale"] = True
    accumulator["currentConfrontation"]["games"].append(game)
    return accumulator


def hydrate(edition):
    id = edition["id"]
    edition = hydrate_with_squads(edition)
    coachsById = get_coachs_by_id(edition)
    edition["coachs"] = [coach for coach in coachsById.values()]
    edition = hydrate_with_games(edition, coachsById)
    edition = hydrate_with_rankings(edition)
    return edition


def extract_row(index, result, headers):
    def fix_header(header):
        return "opponentsPoints" if header == "opponentPoints" else header

    return [index + 1, result["name"]] + [
        result[fix_header(header)] for header in headers
    ]

TRANSLATED={
    "points": "Points",
    "opponentsPoints": "Points adverses",
    "netTd": "Différence de TD",
    "netCasualties": "Différence de sorties",
    "casualtiesFor": "Sorties",
    "tdFor": "Touchdowns",
    "foulsFor": "Agressions",
    "tdAgainst": "Touchdowns encaissés",
    "diffRanking":"Différence de classement",
    "firstDayRanking":"Classement du premier jour",
    "finalRanking":"Classement final",
    "coachTeamPoints":"Points d'équipe",
    "win":"Victoires",
    "draw":"Nuls",
    "opponentsCoachTeamPoints": "Points d'équipe adverses",
    "main":"",
    "comeback":"du meilleur retour",
    "td":"du meilleur marqueur",
    "fouls":"du plus vil agresseur",
    "casualties":"du meilleur sorteur",
    "defense":"de la meilleure défense",
    "mainSquad":"",
    "comebackSquad":"du meilleur retour",
    "tdSquad":"des meilleurs marqueurs",
    "foulsSquad":"des plus vils agresseurs",
    "casualtiesSquad":"des meilleurs sorteurs",
    "defenseSquad":"de la meilleure défense"
}

def translate(key):
    return TRANSLATED[key] if key in TRANSLATED else key


def hydrate_with_rankings(edition):
    id = edition["id"]
    edition["coachRanking"] = []
    edition["squadRanking"] = []
    if "coach" in edition["rankings"]:
        for rankingName in edition["rankings"]["coach"]:
            ranking = {"name": translate(rankingName)}
            headers = [
                column for column in edition["rankings"]["coach"][rankingName]
            ]
            ranking["headers"] = ["#", "Coach"] + [
                translate(header) for header in headers
            ]
            requestedranking = get_from_ws(f"ranking/coach/{rankingName}/{id}")
            ranking["rows"] = [
                extract_row(index, result, headers)
                for index, result in enumerate(requestedranking)
            ]
            edition["coachRanking"].append(ranking)
    if "coachTeam" in edition["rankings"]:
        for rankingName in edition["rankings"]["coachTeam"].keys():
            ranking = {"name": translate(rankingName+'Squad')}
            headers = [
                column for column in edition["rankings"]["coachTeam"][rankingName]
            ]
            ranking["headers"] = ["#", " Équipe"] + [
                translate(header) for header in headers
            ]
            requestedranking = get_from_ws(f"ranking/coachTeam/{rankingName}/{id}")
            ranking["rows"] = [
                extract_row(index, result, headers)
                for index, result in enumerate(requestedranking)
            ]
            edition["squadRanking"].append(ranking)
    return edition


def hydrate_with_games(edition, coachsById):
    id = edition["id"]
    edition["games"] = []
    for round in range(0, edition["roundNumber"]):
        requestedgames = get_from_ws(f"MatchList/{id}/{round+1}")
        games = [add_squad_id_to_game(game, coachsById) for game in requestedgames]
        games.sort(reverse=True, key=lambda game: game["finale"])
        edition["games"].append(games)

        if edition["fullTriplette"]:
            accumulator = functools.reduce(
                reduce_game_to_confrontations,
                games,
                {
                    "currentSquadId": None,
                    "confrontations": [],
                    "currentConfrontation": None,
                },
            )
            accumulator["confrontations"].append(accumulator["currentConfrontation"])
            edition["confrontations"].append(accumulator["confrontations"])
    return edition


def hydrate_with_squads(edition):
    id = edition["id"]
    # We need squads if tournament is squadCompetition
    if edition["fullTriplette"]:
        edition["confrontations"] = []
        requestedsquads = get_from_ws(f"CoachTeamList/{id}")
        edition["squads"] = requestedsquads.values()
    return edition


def get_coachs_by_id(edition):
    id = edition["id"]
    return get_from_ws(f"CoachList/{id}")


if __name__ == "__main__":
    editions = get_from_ws("Editions")
    ids = [edition["id"] for edition in editions]
    hydratedEditions = [hydrate(edition) for edition in editions]
    generate_editions(prepare_editions(hydratedEditions), ids)
