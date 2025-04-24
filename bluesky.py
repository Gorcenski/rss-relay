from functools import partial
import html
import os
from io import BytesIO
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
        
        embed_external = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=post.title,
                description=html.unescape(post.description),
                uri=post.link,
                thumb=thumb_blob
            ))
        
        tb = client_utils.TextBuilder()
        comment = cls.trim_post(post.title, post.comment)
        client.send_post(tb.link(post.title, post.link).text(f"\n\n{comment}"),
                         embed=embed_external)
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
    