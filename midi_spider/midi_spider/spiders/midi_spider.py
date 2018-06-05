import re
import scrapy
from midi_spider.items import MIDIFile
from scrapy.linkextractors import LinkExtractor


class MIDISpider(scrapy.Spider):
    name = "midi"
    start_urls = ["http://www.limburgzingt.nl/plaatsen.htm"]

    def parse(self, response):
        for link in LinkExtractor().extract_links(response):
            yield response.follow(link, self.parse_midi_links)

    def parse_midi_links(self, response):
        out = []
        links = response.xpath("//a/@href").re(r".*\.mid")
        for l in links:
            link = MIDIFile()
            m = re.match(r"(.+)\/([^/]+)\.(.*)", l)
            if m:
                link["name"] = m.group(2)
            else:
                link["name"] = l
            link["origin_url"] = response.url
            link["link"] = response.urljoin(l)
            link["file_urls"] = [link["link"]]
            out.append(link)
        return out
