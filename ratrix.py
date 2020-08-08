import requests # external import
import urllib
import sys

from PIL import Image, ImageDraw, ImageFont

API_KEY = "d5ce1034"

def build_request(**kwargs):
    global API_KEY
    req = "https://www.omdbapi.com/?apikey=" + API_KEY
    for arg in kwargs:
        req += "&" + arg + "=" + urllib.parse.quote(str(kwargs[arg]), safe='')
    return requests.get(req)

def search(name):
    global API_KEY
    r = build_request(t=name)
    if r.status_code == 404:
        return None
    return r.json()

def get_season_details(response):
    num_seasons = int(response["totalSeasons"])
    season_details = []
    for season in range(1, num_seasons + 1):
        res = build_request(t=response["Title"], Season=season)
        if res.status_code == 404:
            res = None
        else:
            res = res.json()
        season_details.append(res)
    return season_details

def get_episode_details(season_details):
    episode_details = []
    for season in season_details:
        if season == None:
            episode_details.append([])
            continue
        season_wise_episodes = []
        episodes = season["Episodes"]
        for episode in episodes:
            season_wise_episodes.append((episode["Title"], episode["Episode"], episode["imdbRating"]))
        season_wise_episodes = sorted(season_wise_episodes, key=lambda x: x[1])
        episode_details.append(season_wise_episodes)
    return episode_details

def hex_to_rgb(h):
    return tuple(int(h.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

# colors should follow the sequence:
# background, foreground, header, worst, good, best, N/A

# gruvbox colors
GRUVBOX = ["#282828", "#ebdbb2", "#458588", "#cc241d", "#d79921", "#98971a", "#8ec07c"]

COLORS = [hex_to_rgb(i) for i in GRUVBOX]

# dimension of each box
BOX_HEIGHT = 30
BOX_WIDTH = 30

# padding in all sides of the image
PADDING = 30

# font
FONT = ImageFont.truetype("OpenSans-SemiBold.ttf", 15)

def calculate_index_by_grade(grade):
    # bad < 4.0
    # medium < 8.0
    # best > 8.0
    index = 3
    if grade > 4.0:
        index += 1
    if grade > 8.0:
        index += 1
    return index

def draw_row(im, start, text, grades=False):
    global BOX_HEIGHT, BOX_WIDTH, FONT
    # im contains the ImageDraw object.
    # start contains the starting coordinate of the row.
    # text is a iterable which contains the text for the row.
    # grades denote whether or not the row is a grade value, and
    # hence whether or not a contextual color value should be
    # chosen as the background. by default, COLORS[1] is chosen.
    i = 0
    current_left = start[0]
    top = start[1]
    for cell in text:
        left = current_left
        right = left + BOX_WIDTH
        bottom = top + BOX_HEIGHT
        current_left = right
        if cell == None:
            continue
        rect_dim = (left, top, right, bottom)
        rect_color = COLORS[2]
        # 1) we don't color the first cell, because it is the row header.
        # 2) for N/A cells, we set to a specific color
        if cell == "N/A":
            rect_color = COLORS[-1]
        elif i > 0 and grades:
            rect_color = COLORS[calculate_index_by_grade(float(cell))]
        im.rectangle(rect_dim, fill=rect_color, outline=COLORS[0])
        # center the text
        cell = str(cell)
        textsize = im.textsize(cell, font=FONT)
        pad_left = (BOX_WIDTH - textsize[0]) / 2
        pad_top = (BOX_HEIGHT - textsize[1]) / 2
        im.text((left + pad_left, top + pad_top), cell, fill=COLORS[1], font=FONT)
        i += 1


def generate_image(show, episode_details, filename):
    global BOX_WIDTH, BOX_HEIGHT, PADDING, FONT
    # we need to draw a number_of_seasons x max_ep_in_a_season matrix
    num_seasons = len(episode_details)
    max_ep_in_a_season = len(max(episode_details, key=lambda x: len(x)))
    min_height = BOX_HEIGHT * (max_ep_in_a_season + 1) # we need to draw the season row
    min_width = BOX_WIDTH * (num_seasons + 1) # we need to draw ep column
    height = min_height + (PADDING * 2)
    width = min_width + (PADDING * 2)

    # create the image
    im = Image.new('RGB', (width, height), COLORS[0])
    draw = ImageDraw.Draw(im)
    # draw the name
    namesize = draw.textsize(show["Title"], font=FONT)
    pad_left = (width - namesize[0]) / 2
    pad_top = (PADDING - namesize[1]) / 2
    draw.text((pad_left, pad_top), show["Title"], fill=COLORS[1], font=FONT)
    # draw the seasons header
    seasons_header = [i for i in range(1, len(episode_details) + 1)]
    seasons_header.insert(0, None)
    draw_row(draw, (PADDING, PADDING), seasons_header)
    current_top = PADDING + BOX_HEIGHT

    sc = 1
    for i in range(max_ep_in_a_season):
        ratings = [sc]
        for season in episode_details:
            if len(season) > i:
                ratings.append(season[i][2])
        draw_row(draw, (PADDING, current_top), ratings, True)
        current_top = current_top + BOX_HEIGHT
        sc += 1

    im.save(filename)

def main():
    if len(sys.argv) < 3:
        print("Usage: %s <show_to_search> <output_file>" % sys.argv[0])
        sys.exit(1)
    show = search(sys.argv[1])
    if show != None:
        seasons = get_season_details(show)
        episodes = get_episode_details(seasons)
        generate_image(show, episodes, sys.argv[2])
    else:
        print("Error: Unable to get details about '%s'" % sys.argv[1])

if __name__ == "__main__":
    main()
