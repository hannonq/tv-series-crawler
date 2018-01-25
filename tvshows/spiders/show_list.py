# -*- coding: utf-8 -*-
import re
from collections import OrderedDict

from bs4 import BeautifulSoup
from bs4.element import NavigableString
from bs4.element import Tag
from pymongo import MongoClient
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from tvshows.items import TvshowItem
from tvshows.items import TvshowItemLoader

client = MongoClient()


class ShowListSpider(CrawlSpider):
    name = 'show_list'
    start_urls = ['http://eztv.ag/showlist/']
    BASE_URL = 'https://eztv.ag'

    rules = (
        Rule(LinkExtractor(allow=('/shows/')), callback='parse_show'),
    )

    def parse_show(self, response):
        """Entry point to parse each TV show"""

        self.logger.info('Starting to parse the url %s', response.url)

        # Get the HTML into a BeautifulSoup object
        soup = BeautifulSoup(response.text, 'lxml')

        # Find the properties in the document
        name = soup.find('td', class_='section_post_header').span.text
        description_tags = soup.findAll('span', itemprop='description')
        description_text = '\n'.join([d.text for d in description_tags])
        rating_value = soup.find('span', itemprop='ratingValue').text
        rating_count = soup.find('span', itemprop='ratingCount').text

        # Find all the <b> tags, which contain the airing information
        _air_info = soup.find('td', class_='show_info_airs_status').find_all('b')
        air_day = ''
        status = ''

        # Check if air day and series status were found
        if len(_air_info) >= 2:
            # Gets the air day and splits into a list in case
            # The show is aired multiple days per week
            air_day = _air_info[0].text.split(', ')
            status = _air_info[1].text

        # Get the general info
        _general_info = soup.find('table', class_='section_thread_post show_info_description')
        general_info = self._parse_general_information(str(_general_info), name)

        # Try to parse the episodes' list and the cast list
        # If these operations fail, skip this series
        try:
            seasons = self._parse_episodes_list(soup)
            cast = self._parse_cast(soup)

            item_loader = TvshowItemLoader(TvshowItem(), response=response)

            item_loader.add_value('name', name)
            item_loader.add_value('status', status)
            item_loader.add_value('rating_value', float(rating_value))
            item_loader.add_value('rating_count', int(rating_count))
            item_loader.add_value('air_day', air_day)
            item_loader.add_value('series_premiere', general_info.get('premiere', ''))
            item_loader.add_value('classification', general_info.get('classification', ''))
            item_loader.add_value('genre', general_info.get('genre', ''))
            item_loader.add_value('network', general_info.get('network', ''))
            item_loader.add_value('air_time', general_info.get('air_time', ''))
            item_loader.add_value('runtime', general_info.get('runtime', ''))
            item_loader.add_value('url', response.url)
            item_loader.add_value('description', description_text)
            item_loader.add_value('seasons', seasons)
            item_loader.add_value('cast', cast)

            item = item_loader.load_item()

            self._save_to_json(item)
            self._save_to_mongodb(item)

        except Exception as e:
            self.logger.error("Error parsing series %s. Skipping." % name)
            self.logger.error(e)

            with open('skipped_series.txt', 'a') as skipped:
                skipped.write(name + '\n')
                skipped.write(response.url + '\n')
                skipped.write('\n')

    def _save_to_mongodb(self, item):
        db = client.series_database
        series = db.series
        try:
            series.update(item, item, upsert=True)
        except Exception as e:
            self.logger.error("Couldn't save the series %s to MongoDB" % item.get('name'))
            self.logger.error(e)

    def _save_to_json(self, item):
        import os
        import json
        filename = 'output/%s.json' % item.get('name').replace('/', '-')
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as fp:
            json.dump(dict(item), fp, indent=4)

    def _clean_character_name(self, character_name):
        clean_name = ''
        try:
            clean_name = re.search('(?<= as ).*', character_name).group(0)
        except Exception:
            self.logger.error("Couldn't parse the name %s " % character_name)
        return clean_name

    def _clean_actor_name(self, actor_name):
        return actor_name.replace('.', '')

    def _parse_cast(self, soup):
        cast_column = soup.find('td', class_='show_info_tvnews_column').div

        cast = {}
        first_actor = cast_column.find('div', itemprop='actor')
        first_character = first_actor.next_sibling

        cast[self._clean_actor_name(first_actor.text)] = self._clean_character_name(first_character)

        siblings_list = list(first_character.next_siblings)
        for i in range(0, len(siblings_list) - 1, 2):
            if isinstance(siblings_list[i], Tag) and siblings_list[i].name == 'div':
                try:
                    cast[self._clean_actor_name(siblings_list[i].text)] = self._clean_character_name(
                        siblings_list[i + 1])
                except Exception:
                    self.logger.error("error in parsing cast list")
        return cast

    def _parse_episodes_list(self, soup):
        """
        Parse the episode list.

        Returns the episode list in the following format:

        "seasons": {
            "1": [
                {
                    'ep_number': 1,
                    'ep_name': 'Pilot',
                    'release_date': 'Sep 21, 2009'
                }
            ]
        }

        """

        ep_list = soup.find('div', style='width: 537px; height: 250px; overflow-y: auto;')
        seasons = OrderedDict()

        season_number = '1'
        ep_number = 1
        for i in ep_list:
            if isinstance(i, Tag) and i.name == 'div':
                season_number = re.search('Season (\d+)', i.text).group(1)
                seasons[season_number] = []
                ep_number = 1
            if isinstance(i, NavigableString):
                ep = i.split(' -- ')
                ep_name = ep[-1]
                release_date = ep[1]

                seasons[season_number].append(
                    {
                        'ep_number': ep_number,
                        'ep_name': ep_name,
                        'release_date': release_date
                    }
                )
                ep_number += 1

        return seasons

    def _parse_general_information(self, _general_info, name):
        """Parse the general information.

        Ex:
        Series Premiere: January 20, 2011
        Classification: Talk Show
        Genre: Action | Comedy | News
        Network: Channel 4
        Airs: Thursday at 10:00 pm
        Runtime: 60 Minutes
        """

        def _get_pattern_or_empty(pattern, group=1):
            """Look for each pattern. If can't match, return empty string"""
            try:
                p = re.compile(pattern)
                return p.search(_general_info).group(group)
            except AttributeError:
                attr = pattern.split(':')[0]
                self.logger.warning("'%s' not found for series '%s'. Returning empty string" % (attr, name))
                return ''

        premiere = _get_pattern_or_empty('Series Premiere: ((\w+|,| )+)')
        classification = _get_pattern_or_empty('Classification: ((\w+ ?)+)')
        genre = _get_pattern_or_empty('Genre: ([\w+\| ]+)').split(' | ')
        network = _get_pattern_or_empty('Network: (\w+ ?\w+?)+')
        air_time = _get_pattern_or_empty('Airs: (\w+,? ?)+ at (\d{2}:\d{2} (am|pm))', 2)
        runtime = _get_pattern_or_empty('Runtime: (\d+ Minutes)')

        return {
            'premiere': premiere,
            'classification': classification,
            'genre': genre,
            'network': network,
            'air_time': air_time,
            'runtime': runtime
        }
