""" Core scraper for bitcointalk.org. """
import bitcointalk
import logging
import memoizer
import os
import sys
import traceback
import time
import numpy as np

boardId = 1
# restrict the number of board pages that will be scraped
restrictPageNumTo = 1
restrictTopicNum = 300

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p')

# Make sure we don't rescrape information already in the DB
memoizer.remember()
# start timer to calculate the total execution time of scraping
start = time.time()
logging.info("Beginning scrape of board ID...".format(boardId))
board = memoizer.scrapeBoard(boardId)




numberOfPages = restrictPageNumTo if restrictPageNumTo else board['num_pages']
logging.info("Found {0} topic pages in board...".format(
    board['num_pages']))
logging.info("{0} will be scraped".format(
    numberOfPages))
for boardPageNum in range(1, numberOfPages + 1):
    logging.info(">Scraping page {0}...".format(boardPageNum))
    topicIds = memoizer.scrapeTopicIds(boardId, boardPageNum)    
    # numberOfPages = restrictTopicNum if restrictTopicNum else 0  
    for topicId in topicIds:
        logging.info(">>Starting scrape of topic ID {0}...".format(topicId))
        try:
            topic = memoizer.scrapeTopic(topicId)
        except Exception as e:
            print '-' * 60
            print "Could not request URL for topic {0}:".format(topicId)
            print traceback.format_exc()
            print '-' * 60
            logging.info(">>Could not request URL for topic {0}:".format(
                topicId))
            continue
        logging.info(">>Found {0} message pages in topic...".format(
            topic['num_pages']))
        for topicPageNum in range(1, topic['num_pages'] + 1):
            logging.info(">>>Scraping page {0}...".format(topicPageNum))
            messages = memoizer.scrapeMessages(topic['id'], topicPageNum)
            if not messages:
                logging.info(">>>Exiting current & continuing to next topic: ")
                break
                    
            for message in messages:
                if message['member'] > 0:
                    memoizer.scrapeMember(message['member'])
            logging.info(">>>Done with TOPIC page {0}.".format(topicPageNum))
        logging.info(">>Done scraping topic ID {0}.".format(topicId))
    logging.info(">Done with BOARD page {0}.".format(boardPageNum))

logging.info("All done.")
logging.info("Made {0} requests in total.".format(bitcointalk.countRequested))
# end timer
end = time.time()
logging.info("Total time for scraping forum: " + str(end - start) + " seconds")
# Traceback (most recent call last):
  # File "scrape_boards.py", line 63, in <module>
   # logging.info("Total time for scraping forum: ".end - start)
# AttributeError: 'str' object has no attribute 'end'
