# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

from scrapy.item import Item, Field


class MIDIFile(Item):
    name = Field()
    url = Field()
    link = Field()
    file_urls = Field()
    files = Field()
    origin_url = Field()
