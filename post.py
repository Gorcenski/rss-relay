from dataclasses import dataclass
from functools import partial
from bs4 import BeautifulSoup
from httpx import get
from playwright.sync_api import sync_playwright
from rss_parser.models.rss.item import Item


@dataclass
class Post:
    title: str
    link: str
    guid: str
    description: str
    comment: str
    image: str

    def is_postworthy(self) -> bool:
        return ("started" in self.title) | \
            ("finished reading" in self.title) | \
            ("emilygorcenski.com" in self.guid)

    @staticmethod
    def get_link_url(item : Item) -> str:
        """
        Get the URL of the first link in the item.
        """
        if item.links and len(item.links) > 0:
            return str(item.links[0].content)
        return None

    @staticmethod
    def get_comment(description: str) -> str:
            """
            Extract comment from the description.
            """
            parse = partial(BeautifulSoup, features="html.parser")
            if description:
                return parse(description.split("\n")[0]).get_text()
            return None

    @staticmethod
    def fetch_remote_meta(url):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)
            html = page.content()
            browser.close()
        meta = BeautifulSoup(html, 'html.parser').find_all("meta")
        image = next(filter(lambda x: x.get("property", None) == "og:image",meta), None) or \
                next(filter(lambda x: x.get("name", None) == "og:image", meta), None)
        description = next(filter(lambda x: x.get("property", None) == "og:description",meta), None) or \
                      next(filter(lambda x: x.get("name", None) == "og:description", meta), None)
        if image:
            image = image.get("content")
        if description:
            description = description.get("content")
        return image, description

    @staticmethod
    def get_image(item : Item) -> str:
        """
        Get the URL of the first image in the item.
        """
        try:
            if item.guid.content != Post.get_link_url(item):
                return Post.fetch_remote_meta(Post.get_link_url(item))
            if item.enclosures and len(item.enclosures) > 0:
                return str(item.enclosures[0].attributes.get("url"))
        except Exception as e:
            print(e)
        return None

    def __init__(self, item : Item):
        if item.guid.content != Post.get_link_url(item):
            image, description = self.fetch_remote_meta(self.get_link_url(item))
        else:
            image = str(item.enclosures[0].attributes.get("url"))
            description = self.get_comment(item.description.content)

        self.title          = item.title.content
        self.link           = self.get_link_url(item)
        self.guid           = item.guid.content
        self.description    = description
        self.comment        = self.get_comment(item.description.content)
        self.image          = image
