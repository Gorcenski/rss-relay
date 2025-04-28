import argparse
from dataclasses import dataclass
from functools import partial
from pathlib import Path
import sqlite3
from pipe import Pipe, select, where, traverse
import requests
from rss_parser import RSSParser
from rss_parser.models.rss.item import Item
from bluesky import Bluesky
from post import Post


@Pipe
def load_rss(url : str) -> str:
    """
    Load RSS feed from a given URL.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error loading RSS feed: {e}")
        return None

@Pipe
def save_rss(feed: str, file_name: str) -> str:
    """
    Save RSS feed to a file.
    """
    try:
        with open(file_name, 'w') as f:
            f.write(feed)
        print(f"Feed saved to {file_name}")
    except IOError as e:
        print(f"Error saving feed: {e}")
    return feed

def db_connect():
    Path("data").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect('data/rss.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS posts ("
                   "guid TEXT PRIMARY KEY, "
                   "title TEXT, "
                   "link TEXT, "
                   "description TEXT, "
                   "comment TEXT, "
                   "image TEXT)")
                   
    conn.commit()
    return conn, cursor

def add_post(post, conn, cursor):
    try:
        cursor.execute("INSERT INTO posts (guid, title, link, description, comment, image) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (post.guid,
                         post.title,
                         post.link,
                         post.description,
                         post.comment,
                         post.image))
        conn.commit()
        return post
    except sqlite3.IntegrityError as e:
        return None
    
@Pipe
def parse_rss_to_items(feed : str):
    return RSSParser.parse(feed).channel.items



if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-l",
                        "--load-feed",
                        help="Load a feed from a URL",
                        metavar='URL',
                        type=str)
    parser.add_argument("-s",
                        "--skeet",
                        help="Post to Bluesky",
                        action="store_true")
    args = parser.parse_args()

    
    conn, cursor = db_connect()
    insert_posts = partial(add_post, conn=conn, cursor=cursor)
    new_posts = []
    # future improvement: set the insert and the posting to be atomic
    # so if there's a posting error, a single entry can be rolled back
    # probably not necessary for the primary use case
    try:
        if args.load_feed:
            new_posts = (args.load_feed 
                | load_rss 
                | parse_rss_to_items
                | select(Post)
                | where(lambda x: x.is_postworthy())
                | select(insert_posts)
                | where(lambda x: x is not None)
                | select(lambda x: x.populate_meta()))
    except Exception as e:
        print(f"Error processing feed: {e}")
        conn.close()
        exit(1)
    
    if args.skeet:
        new_posts = new_posts | Pipe(Bluesky.post_skeets)

    list(new_posts)
    
    conn.close()
    