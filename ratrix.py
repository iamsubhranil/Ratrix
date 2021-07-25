import requests  # external import
import urllib
import sys
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

API_KEY = None


def get_api_key():
    if os.path.isfile(".apikey") is False:
        print("Error: Unable to obtain the API key!")
        print("Obtain an API key omdb.com and save in .apikey inside present folder!")
        sys.exit(0)
    global API_KEY
    with open(".apikey", "r") as f:
        API_KEY = f.read().strip()


def build_request(**kwargs):
    global API_KEY
    req = "https://www.omdbapi.com/?apikey=" + API_KEY
    for arg in kwargs:
        req += "&" + arg + "=" + urllib.parse.quote(str(kwargs[arg]), safe='')
    return requests.get(req)


def search(name):
    global API_KEY
    r = build_request(t=name)
    if r.status_code == 404 or r.json()["Response"] == "False":
        return None
    return r.json()


def get_season_details(response):
    num_seasons = int(response["totalSeasons"])
    print("Total seasons: %d.." % num_seasons)
    season_details = []
    showname = response["Title"]
    print("Gathering information about season 000..", end='')
    sys.stdout.flush()
    for season in range(1, num_seasons + 1):
        print("\b\b\b\b\b{:3}..".format(season), end='')
        sys.stdout.flush()
        res = build_request(t=showname, Season=season)
        if res.status_code == 404:
            res = None
        else:
            res = res.json()
        season_details.append(res)
    print(" Done")
    return season_details


def get_episode_details(season_details):
    episode_details = []
    for season in season_details:
        if season is None:
            episode_details.append([])
            continue
        season_wise_episodes = []
        episodes = season["Episodes"]
        for episode in episodes:
            season_wise_episodes.append(
                (episode["Title"], episode["Episode"], episode["imdbRating"]))
        episode_details.append(season_wise_episodes)
    return episode_details


def hex_to_rgb(h):
    return tuple(int(h.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

# colors should follow the sequence:
# background, foreground, header, worst, good, best, N/A


# gruvbox colors
GRUVBOX = ["#282828", "#ebdbb2", "#458588",
           "#cc241d", "#d79921", "#98971a", "#8ec07c"]
# elementary colors
ELEMENTARY = ["#101010", "#f2f2f2", "#101010",
              "#e1321a", "#ffc005", "#6ab017", "#2aa7e7"]

# 0 -> transparent, 1 -> opaque
OPACITY = 0.85
COLORS = [hex_to_rgb(i) for i in ELEMENTARY]

# dimension of each box
BOX_HEIGHT = 50
BOX_WIDTH = 50

# dimension of each marker inside the box
MARKER_WIDTH = 3
MARKER_PADDING_HEIGHT = 10

# padding in all sides of the image
PADDING = 30

# font
FONT = ImageFont.truetype("OpenSans-SemiBold.ttf", 15)
TITLEFONT = ImageFont.truetype("OpenSans-Light.ttf", 35)

# spacing denotes the space between ratings and stat
STAT_SPACING = 30
# padding denotes the left and bottom padding of stat
STAT_PADDING = 30
# denotes the spacing between title and overall rating
NAME_RATING_SPACING = 10


def calculate_index_by_grade(grade):
    # bad < 4.0
    # medium < 8.0
    # best > 8.0
    index = 3
    if grade > 3.9:
        index += 1
    if grade > 7.9:
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
        if cell is None:
            continue
        rect_dim = (left, top + (MARKER_PADDING_HEIGHT / 2), left +
                    MARKER_WIDTH, bottom - (MARKER_PADDING_HEIGHT / 2))
        rect_color = COLORS[0]
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
        pad_left = (BOX_WIDTH - textsize[0] + MARKER_WIDTH) / 2
        pad_top = (BOX_HEIGHT - textsize[1]) / 2
        im.text((left + pad_left, top + pad_top),
                cell, fill=COLORS[1], font=FONT)
        i += 1


def calculate_text_size(text, fnt):
    return fnt.getsize(text)


def calculate_stat_size(name, without_overall=False):
    size = calculate_text_size(name, TITLEFONT)
    name_rate_spacing = NAME_RATING_SPACING
    if without_overall:
        ratings = (0, 0)
        name_rate_spacing = 0
    else:
        ratings = calculate_text_size("10.0", FONT)
    return (size[0] + ratings[0] + name_rate_spacing + (STAT_PADDING * 2), size[1] + STAT_SPACING)


def calculate_ratings_size(name, num_seasons, max_ep_in_a_season):
    global BOX_HEIGHT, BOX_WIDTH, PADDING
    # we need to draw the season row
    min_height = BOX_HEIGHT * (max_ep_in_a_season + 1)
    min_width = BOX_WIDTH * (num_seasons + 1)  # we need to draw ep column
    height = min_height + (PADDING * 2)
    width = min_width + (PADDING * 2)
    stat_width, stat_height = calculate_stat_size(name)
    if width < stat_width:
        PADDING += int((stat_width - width) / 2)
        width = stat_width
        height = min_height + (PADDING * 2)
    height += stat_height
    return width, height


def calculate_size(posterim, name, num_seasons, max_ep_in_a_season):
    # given a minimum size to draw the text,
    # this function resizes the poster or the
    # BOX dimensions to match one another.
    # if the image dimension is larger, then
    # the BOX dims are modified. If the content
    # size is larger, then the image is resized.
    global BOX_WIDTH, BOX_HEIGHT, PADDING
    min_width, min_height = calculate_ratings_size(
        name, num_seasons, max_ep_in_a_season)
    img_width, img_height = posterim.size
    if min_width > img_width:
        img_width = min_width
    else:
        while min_width < img_width:
            # boxes should always be squares
            BOX_WIDTH += 1
            BOX_HEIGHT += 1
            PADDING += 1
            min_width, min_height = calculate_ratings_size(
                name, num_seasons, max_ep_in_a_season)
        img_width = min_width
    if min_height > img_height:
        img_height = min_height
    else:
        while min_height < img_height:
            BOX_HEIGHT += 1
            BOX_WIDTH += 1
            PADDING += 1
            min_width, min_height = calculate_ratings_size(
                name, num_seasons, max_ep_in_a_season)
        img_width = min_width
        img_height = min_height
    return min_width, min_height


def generate_image(show, episode_details, filename):
    global BOX_WIDTH, BOX_HEIGHT, PADDING, FONT
    # we need to draw a number_of_seasons x max_ep_in_a_season matrix
    num_seasons = len(episode_details)
    max_ep_in_a_season = len(max(episode_details, key=lambda x: len(x)))
    # dynamically adjust the poster
    print("Downloading poster..")
    poster = Image.open(urllib.request.urlopen(show["Poster"]))
    print("Adjusting the image dimensions..")
    width, height = calculate_size(
        poster, show["Title"], num_seasons, max_ep_in_a_season)
    # resize and blur the poster
    print("Resizing and blurring the poster..")
    poster = poster.resize((width, height))
    poster = poster.filter(ImageFilter.GaussianBlur(radius=5))
    # create the image
    print("Creating matrix image..")
    im = Image.new('RGB', (width, height), COLORS[0])
    draw = ImageDraw.Draw(im)
    # draw the row column headers
    print("Drawing seasons and episode headers..")
    column_header_size = calculate_text_size("Seasons", FONT)
    draw.text((((width - column_header_size[0]) / 2) + (BOX_WIDTH / 2),
              PADDING - column_header_size[1]), "Seasons", fill=COLORS[1], font=FONT)
    row_header_size = calculate_text_size("Episodes", FONT)
    row_header_img = Image.new(
        'RGB', (row_header_size[0], row_header_size[0]), COLORS[0])
    row_header_draw = ImageDraw.Draw(row_header_img)
    row_header_draw.text((0, 0), "Episodes", fill=COLORS[1], font=FONT)
    row_header_pos_left = row_header_size[0] - row_header_size[1]
    row_header_img = row_header_img.rotate(270)
    row_header_img = row_header_img.crop(
        (row_header_pos_left, 0, row_header_pos_left + row_header_size[1], row_header_size[0]))
    row_header_img = row_header_img.rotate(180)
    im.paste(row_header_img, ((
        PADDING - row_header_size[1]), int((height - row_header_size[0]) / 2)))
    # draw the seasons header
    seasons_header = [i for i in range(1, len(episode_details) + 1)]
    seasons_header.insert(0, None)
    draw_row(draw, (PADDING, PADDING), seasons_header)
    current_top = PADDING + BOX_HEIGHT

    print("Drawing ratings..")
    for i in range(max_ep_in_a_season):
        ratings = [i + 1]
        for season in episode_details:
            if len(season) > i:
                ratings.append(season[i][2])
            else:
                ratings.append(None)
        draw_row(draw, (PADDING, current_top), ratings, True)
        current_top = current_top + BOX_HEIGHT

    print("Drawing show name and overall rating..")
    # write show name
    name_width, name_height = calculate_text_size(show["Title"], TITLEFONT)
    rating_width, rating_height = calculate_text_size(show["imdbRating"], FONT)
    draw.text((STAT_PADDING, height - name_height - STAT_PADDING),
              show["Title"], fill=COLORS[1], font=TITLEFONT)

    orate_left = STAT_PADDING + name_width + NAME_RATING_SPACING
    orate_top = height - name_height - STAT_PADDING
    orate_bottom = orate_top + rating_height
    orate_right = orate_left + (MARKER_WIDTH / 2)
    orate = show["imdbRating"]
    draw.rectangle((orate_left, orate_top, orate_right, orate_bottom),
                   fill=COLORS[calculate_index_by_grade(float(orate))])
    draw.text((orate_right + 5, orate_top),
              show["imdbRating"], fill=COLORS[1], font=FONT)

    print("Blending with the poster..")
    finalimage = Image.blend(poster, im, OPACITY)
    print("Saving the resulting image..")
    finalimage.save(filename)
    print("Completed successfully!")


def main():
    if len(sys.argv) < 3:
        print("Usage: %s <show_to_search> <output_file>" % sys.argv[0])
        sys.exit(1)
    get_api_key()
    print("Searching for '%s'.." % sys.argv[1])
    show = search(sys.argv[1])
    if show is not None:
        try:
            print("Gathering information about '%s'.." % show["Title"])
            seasons = get_season_details(show)
            episodes = get_episode_details(seasons)
            generate_image(show, episodes, sys.argv[2])
        except KeyError as e:
            print("Error: Data does not conform to the expected format!")
            print("The following value could not be found:", e)
            print("Unable to generate the matrix!")
    else:
        print("Error: Unable to get details about '%s'!" % sys.argv[1])


if __name__ == "__main__":
    main()
