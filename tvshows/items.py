# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy.loader import ItemLoader

from scrapy.loader.processors import TakeFirst, Identity


class TvshowItemLoader(ItemLoader):
    default_output_processor = TakeFirst()


class TvshowItem(scrapy.Item):
    # define the fields for your item here like:
    _id = scrapy.Field()
    name = scrapy.Field()
    status = scrapy.Field()
    rating_value = scrapy.Field()
    rating_count = scrapy.Field()
    url = scrapy.Field()

    description = scrapy.Field()
    series_premiere = scrapy.Field()
    classification = scrapy.Field(output_processor=Identity())
    genre = scrapy.Field(output_processor=Identity())
    network = scrapy.Field()
    air_day = scrapy.Field(output_processor=Identity())
    air_time = scrapy.Field()
    runtime = scrapy.Field()
    episodes = scrapy.Field()
    cast = scrapy.Field()
    seasons = scrapy.Field()
