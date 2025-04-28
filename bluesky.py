from functools import partial
import html
import os
from io import BytesIO
import re
from PIL import Image
from atproto import Client, models, client_utils
from dotenv import load_dotenv
import httpx
from sharer import Sharer
from post import Post


class Bluesky(Sharer):
    @classmethod
    def trim_post(cls, title : str, comment : str):
        """
        Trim the post to fit within the character limit.
        """
        newline = "\n\n"
        ellipsis = "…"
        max_length = 300
        max_comment = max_length - len(title) - len(newline) - 1
        if len(comment) > max_comment:
            limit = max_comment - len(ellipsis)
            idx = comment[:limit].rfind(" ")
            comment = comment[:idx] + ellipsis
        return comment

    @classmethod
    def resize_image(cls, img_data):
        image = Image.open(BytesIO(img_data))
        image.thumbnail((1024, 1024))  # Resize to fit within 1024x1024
        buffer = BytesIO()
        image.save(buffer, format=image.format)
        img_data = buffer.getvalue()
        return img_data

    @classmethod
    def post_skeet(cls, post : Post, client : Client = None):
        # we need to manually construct the link card, to do that we need to download the image manually
        thumb_blob = None
        if post.image:
            # need to check for size somehow
            img_data = httpx.get(post.image).content
            if img_data:
                # check if the image is too large
                img_data = img_data if len(img_data) < 1000000 \
                                    else cls.resize_image(img_data)
                thumb_blob = client.upload_blob(img_data).blob  
        if thumb_blob or post.description:
            embed_external = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    title=post.title,
                    description=None
                                if not post.description
                                else html.unescape(post.description),
                    uri=post.link,
                    thumb=thumb_blob
                ))
        else:
            embed_external = None
        
        tb = client_utils.TextBuilder()
        if "bookwyrm" in post.link:
            splits = re.split(r"(Emily Gorcenski )([a-z]+)( reading )", post.title)
            title_idx = splits[-1].rfind(" by")
            title = splits[-1][0:title_idx]
            byline = splits[-1][title_idx:]
            comment = post.comment.replace(f"(comment on {title})", "")
            comment = cls.trim_post(post.title, comment)
            body = tb.text("".join(splits[0:-1]).replace("Emily Gorcenski", "I")) \
                     .link(title, post.link) \
                     .text(re.sub("(\n)+", " ", byline)) \
                     .text(f"\n\n{comment}")
        
        else:
            comment = cls.trim_post(post.title, post.comment)
            body = tb.link(post.title, post.link).text(f"\n\n{comment}")
        client.send_post(body, embed=embed_external)
        return post

    @classmethod
    def post_skeets(cls, posts : list[Post]):
        """
        Post a list of skeets to Bluesky.
        """
        load_dotenv()
        client = Client()
        client.login(os.environ["BLUESKY_USERNAME"],
                     os.environ["BLUESKY_PASSWORD"])
        submit_post = partial(cls.post_skeet, client=client)
        return map(submit_post, posts)
    