""" Module for requesting data from bitcointalk.org and parsing it. """
import codecs
from datetime import date
from datetime import datetime
from datetime import time as tm
import HTMLParser
import json
import logging
import lxml.html
from lxml import etree
import requests
import os
from random import random
import re
import sys
import time
import unittest

baseUrl = "https://bitcointalk.org/index.php"
countRequested = 0
interReqTime = 1
lastReqTime = None
date_scrape_limit = "2017-11-10"

def _request(payloadString):
    """Private method for requesting an arbitrary query string."""
    global countRequested
    global lastReqTime
    if lastReqTime is not None and time.time() - lastReqTime < interReqTime:
        #timeToSleep = random()*(interReqTime-time.time()+lastReqTime)*2
        timeToSleep = random()*(interReqTime-time.time()+lastReqTime)
        logging.info("Sleeping for {0} seconds before request.".format(
            timeToSleep))
        time.sleep(timeToSleep)
    logging.info("Issuing request for the following payload: {0}".format(
        payloadString))
    r = requests.get("{0}?{1}".format(baseUrl, payloadString))
    lastReqTime = time.time()
    countRequested += 1
    if r.status_code == requests.codes.ok:
        return r.text
    else:
        raise Exception("Could not process request. \
            Received status code {0}.".format(r.status_code))


def requestBoardPage(boardId, topicOffest=0):
    """Method for requesting a board."""
    logging.info("request: board={0}.{1};sort=last_post;desc".format(boardId, topicOffest))
    return _request("board={0}.{1};sort=last_post;desc".format(boardId, topicOffest))


def requestProfile(memberId):
    """Method for requesting a profile."""
    return _request("action=profile;u={0}".format(memberId))


def requestTopicPage(topicId, messageOffset=0):
    """Method for requesting a topic page."""
    """CAVEAT: Note that a single request will return only 20 messages."""
    return _request("topic={0}.{1}".format(topicId, messageOffset))


def parseBoardPage(html):
    """Method for parsing board HTML. Will extract topic IDs."""
    data = {}

    # Extract name
    docRoot = lxml.html.fromstring(html)
    data['name'] = docRoot.cssselect("title")[0].text

    # Parse through board hierarchy
    bodyArea = docRoot.cssselect("#bodyarea")[0]
    linkNodes = bodyArea.cssselect("div > div > div")[0].cssselect("a.nav")
    data['container'] = None
    data['parent'] = None
    for linkNode in linkNodes:
        link = linkNode.attrib["href"]
        linkText = linkNode.text
        linkSuffix = link.split(baseUrl)[1]
        # If this is the top level of the board continue
        if linkSuffix == '':
            continue
        # If this is the container (second to the top level)
        elif linkSuffix[0] == '#':
            data['container'] = linkText
        # If we have something between the board and the container
        elif linkText != data['name']:
            data['parent'] = int(linkSuffix[7:].split(".")[0])
        elif linkText == data['name']:
            data['id'] = int(linkSuffix[7:].split(".")[0])

    # Parse number of pages
    data['num_pages'] = 0
    pageNodes = bodyArea.cssselect(
        "#bodyarea>table td.middletext>a,#bodyarea>table td.middletext>b")
    for pageNode in pageNodes:
        if pageNode.text == " ... " or pageNode.text == "All":
            continue
        elif int(pageNode.text) > data['num_pages']:
            data["num_pages"] = int(pageNode.text)

    # Parse the topic IDs
    topicIds = []
    topics = docRoot.cssselect(
        "#bodyarea>div.tborder>table.bordercolor>tr")
    for topic in topics:
        # print topic.text_content()
        topicCells = topic.cssselect("td")
        
        
        
        if len(topicCells) != 7:
            continue
        topicLinks = topicCells[2].cssselect("span>a")
        

        
        
        if len(topicLinks) > 0:
            linkPayload = topicLinks[0].attrib['href'].replace(
                baseUrl, '')[1:]
            if linkPayload[0:5] == 'topic':
                topicIds.append(int(linkPayload[6:-2]))
    data['topic_ids'] = topicIds

    return data


def parseProfile(html, todaysDate=datetime.utcnow().date()):
    """Method for parsing profile HTML."""
    data = {}

    docRoot = lxml.html.fromstring(html)

    # Pull the member ID
    pLink = docRoot.cssselect("#bodyarea td.windowbg2 > a")[0].attrib['href']
    data['id'] = int(pLink.split("u=")[1].split(";")[0])

    # Pull associated information
    infoTable = docRoot.cssselect("#bodyarea td.windowbg > table")[0]
    infoRows = infoTable.cssselect("tr")
    labelMapping = {
        "Name: ": "name",
        "Position: ": "position",
        "Date Registered: ": "date_registered",
        "Last Active: ": "last_active",
        "Email: ": "email",
        "Website: ": "website_name",
        "Bitcoin Address: ": "bitcoin_address",
        "Other contact info: ": "other_contact_info"
    }
    for label, key in labelMapping.iteritems():
        data[key] = None
    data['website_link'] = None
    data['signature'] = None
    for row in infoRows:
        columns = row.cssselect("td")
        if len(columns) != 2:
            signature = row.cssselect("div.signature")
            if len(signature) == 0:
                continue
            else:
                sigText = lxml.html.tostring(signature[0])
                sigText = sigText.split('<div class="signature">')[1]
                sigText = sigText.split('</div>')[0]
                data['signature'] = sigText
        else:
            label = columns[0].text_content()
            if label in labelMapping:
                data[labelMapping[label]] = columns[1].text_content().strip()
            if label == "Website: ":
                linkNode = columns[1].cssselect("a")[0]
                data['website_link'] = linkNode.attrib['href']
            elif label == "Date Registered: " or label == "Last Active: ":
                data[labelMapping[label]] = data[labelMapping[label]].replace(
                    "Today at", todaysDate.strftime("%B %d, %Y,"))
                data[labelMapping[label]] = datetime.strptime(
                    data[labelMapping[label]], "%B %d, %Y, %I:%M:%S %p")
    return data


def parseTopicPage(html, todaysDate=datetime.utcnow().date()):
    """Method for parsing topic HTML. Will extract messages."""
    data = {}
    h = HTMLParser.HTMLParser()
    docRoot = lxml.html.fromstring(html)

    # Parse the topic name
    data['name'] = docRoot.cssselect("title")[0].text

    # Parse through board hierarchy for the containing board ID and topic ID
    bodyArea = docRoot.cssselect("#bodyarea")[0]
    nestedDiv = bodyArea.cssselect("div > div > div")
    if len(nestedDiv) == 0:
        raise Exception("Page does not have valid topic data.")
    linkNodes = nestedDiv[0].cssselect("a.nav")
    for linkNode in linkNodes:
        link = linkNode.attrib["href"]
        linkText = linkNode.text
        linkSuffix = link.split(baseUrl)[1]
        if linkSuffix == '' or linkSuffix[0] == '#':
            continue
        elif linkSuffix[0:6] == "?board":
            data['board'] = int(linkSuffix[7:].split(".")[0])
        elif linkText == data['name']:
            data['id'] = int(linkSuffix[7:].split(".")[0])

    # Parse the total count of pages in the topic
    data['num_pages'] = 0
    pageNodes = bodyArea.cssselect(
        "#bodyarea>table td.middletext>a,#bodyarea>table td.middletext>b")
    for pageNode in pageNodes:
        if pageNode.text == " ... " or pageNode.text == "All":
            continue
        elif int(pageNode.text) > data['num_pages']:
            data["num_pages"] = int(pageNode.text)

    # Parse the read count
    tSubj = docRoot.cssselect("td#top_subject")[0].text.strip()
    data['count_read'] = int(tSubj.split("(Read ")[-1].split(" times)")[0])

    # Parse the messages
    messages = []
    firstPostClass = None
    posts = docRoot.cssselect(
        "form#quickModForm>table.bordercolor>tr")
    for post in posts:
        if firstPostClass is None:
            firstPostClass = post.attrib["class"]

        if ("class" not in post.attrib or
                post.attrib["class"] != firstPostClass):
            continue
        else:
            m = {}
            m['topic'] = data['id']
            innerPost = post.cssselect("td td.windowbg,td.windowbg2 tr")[0]

            # Parse the member who's made the post
            userInfoPossible = innerPost.cssselect("td.poster_info>b>a")
            if len(userInfoPossible) > 0:
                userInfo = innerPost.cssselect("td.poster_info>b>a")[0]
                userUrlPrefix = "{0}?action=profile;u=".format(baseUrl)
                m['member'] = int(userInfo.attrib["href"].split(
                    userUrlPrefix)[-1])
            # If no links, then we have a guest
            else:
                m['member'] = 0

            # Parse label information about the post
            subj = innerPost.cssselect(
                "td.td_headerandpost>table>tr>td>div.subject>a")[0]
            m['subject'] = subj.text
            m['link'] = subj.attrib['href']
            m['id'] = long(m['link'].split('#msg')[-1])

            # Parse the message post time
            postTime = innerPost.cssselect(
                "td.td_headerandpost>table>tr>td>div.smalltext")[0]
            m['post_time'] = postTime.text_content().strip().replace(
                "Today at", todaysDate.strftime("%B %d, %Y,"))
            
            m['post_time'] = datetime.strptime(
                m['post_time'], "%B %d, %Y, %I:%M:%S %p")
            #logging.info(">>Starting scrape of topic ID {0}...".format(datetime.strptime("2017-06-01", "%Y-%m-%d") > datetime.now()))
            #logging.info(m['post_time'].strftime("%Y-%m-%d") > datetime.now().strftime("%Y-%m-%d"))
            #logging.info(m['post_time'].strftime("%Y-%m-%d"))
            #logging.info(m['post_time'].strftime("%Y-%m-%d") < "2017-06-01")
            
            #do not scrape pots that are older than the given date
            if m['post_time'].strftime("%Y-%m-%d") < date_scrape_limit:
                break
            # Parse the topic position
            messageNumber = innerPost.cssselect(
                "td.td_headerandpost>table>tr>td>div>a.message_number")[0]
            m['topic_position'] = int(messageNumber.text[1:])

            # Extract the content
            corePost = innerPost.cssselect("div.post")[0]
            
            #get quote
            #topicQuotes = innerPost.cssselect("div.post>div.quoteheader")[0]
            #logging.info((etree.tostring(topicQuotes, pretty_print=True)))
            quote = {}
            quote['quote'] = []
            #m['content_quote'].append(1)
            
            m['content'] = lxml.html.tostring(corePost).strip()[18:-6]
            m['content_no_html'] = corePost.text_content()
            for child in corePost.iterchildren():
                if (child.tag == "div" and 'class' in child.attrib and
                    (child.attrib['class'] == 'quoteheader' or
                        child.attrib['class'] == 'quote')):
                    quote['quote'].append(child)
                    corePost.remove(child)
            m['content_no_quote'] = lxml.html.tostring(corePost).strip()[18:-6]
            m['content_no_quote_no_html'] = corePost.text_content()
            
            quoteString = ""
            for quotetext in quote['quote']:
                #quoteString += lxml.html.tostring(quotetext)
                quoteString += quotetext.text_content()
            #logging.info(quoteString)
            #m['quote'] = quoteString
            m['quote'] = quoteString
            
            messages.append(m)
    
    #print('\n'.join([','.join(['{:4}'.format(item) for item in row]) for row in messages]) )
    #import numpy as np
    #messages_np = np.array(messages)
    #print messages_np
    
    data['messages'] = messages
    return data


class BitcointalkTest(unittest.TestCase):

    """"Testing suite for bitcointalk module."""

    def testRequestBoardPage(self):
        """Method for testing requestBoardPate."""
        html = requestBoardPage(74)
        f = codecs.open("{0}/data/test_board_74.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'w', 'utf-8')
        f.write(html)
        f.close()
        title = lxml.html.fromstring(html).cssselect("title")[0].text
        errorMsg = "Got unexpected output for webpage title: {0}".format(title)
        self.assertEqual(title, "Legal", errorMsg)

        html = requestBoardPage(5, 600)
        f = codecs.open("{0}/data/test_board_5.600.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'w', 'utf-8')
        f.write(html)
        f.close()

    def testRequestProfile(self):
        """Method for testing requestProfile."""
        html = requestProfile(12)
        f = codecs.open("{0}/data/test_profile_12.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'w', 'utf-8')
        f.write(html)
        f.close()
        title = lxml.html.fromstring(html).cssselect("title")[0].text
        errorMsg = "Got unexpected output for webpage title: {0}".format(title)
        self.assertEqual(title, "View the profile of nanaimogold", errorMsg)

    def testRequestTopicPage(self):
        """Method for testing requestTopicPage."""
        html = requestTopicPage(14)
        f = codecs.open("{0}/data/test_topic_14.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'w', 'utf-8')
        f.write(html)
        f.close()
        title = lxml.html.fromstring(html).cssselect("title")[0].text
        errorMsg = "Got unexpected output for webpage title: {0}".format(title)
        self.assertEqual(title, "Break on the supply's increase", errorMsg)

        html = requestTopicPage(602041, 12400)
        f = codecs.open("{0}/data/test_topic_602041.12400.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'w', 'utf-8')
        f.write(html)
        f.close()

    def testParseBoardPage(self):
        """Method for testing parseBoardPage."""
        f = codecs.open("{0}/example/board_74.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'r', 'utf-8')
        html = f.read()
        f.close()
        data = parseBoardPage(html)
        topicIds = data.pop("topic_ids")
        expectedData = {
            'id': 74,
            'name': 'Legal',
            'container': 'Bitcoin',
            'parent': 1,
            'num_pages': 23,
        }
        self.assertEqual(data, expectedData)
        self.assertEqual(len(topicIds), 40)
        self.assertEqual(topicIds[0], 96118)
        self.assertEqual(topicIds[-1], 684343)

        f = codecs.open("{0}/example/board_5.600.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'r', 'utf-8')
        html = f.read()
        f.close()
        data = parseBoardPage(html)
        topicIds = data.pop("topic_ids")
        expectedData = {
            'id': 5,
            'name': 'Marketplace',
            'container': 'Economy',
            'parent': None,
            'num_pages': 128,
        }
        self.assertEqual(data, expectedData)
        self.assertEqual(len(topicIds), 40)
        self.assertEqual(topicIds[0], 423880)
        self.assertEqual(topicIds[-1], 430401)

    def testParseProfile(self):
        """Method for testing parseProfile."""
        f = codecs.open("{0}/example/profile_12.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'r', 'utf-8')
        html = f.read()
        f.close()
        todaysDate = date(2014, 7, 29)
        data = parseProfile(html, todaysDate)
        expectedData = {
            'id': 12,
            'name': 'nanaimogold',
            'position': 'Sr. Member',
            'date_registered': datetime(2009, 12, 9, 19, 23, 55),
            'last_active': datetime(2014, 7, 29, 0, 38, 1),
            'email': 'hidden',
            'website_name': 'Nanaimo Gold Digital Currency Exchange',
            'website_link': 'https://www.nanaimogold.com/',
            'bitcoin_address': None,
            'other_contact_info': None,
            'signature': '<a href="https://www.nanaimogold.com/" ' +
            'target="_blank">https://www.nanaimogold.com/</a> ' +
            '- World\'s first bitcoin exchange service'
        }
        self.assertEqual(data, expectedData)

    def testParseTopicPage(self):
        """Method for testing parseTopicPage."""
        f = codecs.open("{0}/example/topic_14.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'r', 'utf-8')
        html = f.read()
        f.close()
        data = parseTopicPage(html)
        messages = data['messages']
        del data['messages']
        expectedData = {
            'id': 14,
            'name': 'Break on the supply\'s increase',
            'board': 7,
            'count_read': 3051,
            'num_pages': 1
        }
        self.assertEqual(data, expectedData)

        self.assertEqual(len(messages), 2)

        firstMessage = messages[0]
        firstMessageContent = {
            'raw': firstMessage['content'],
            'no_html': firstMessage['content_no_html'],
            'no_quote': firstMessage['content_no_quote'],
            'no_quote_no_html': firstMessage['content_no_quote_no_html']
        }
        del firstMessage['content']
        del firstMessage['content_no_html']
        del firstMessage['content_no_quote']
        del firstMessage['content_no_quote_no_html']

        expectedFirstMessage = {
            'id': long(53),
            'member': 16,
            'subject': 'Break on the supply\'s increase',
            'link': 'https://bitcointalk.org/index.php?topic=14.msg53#msg53',
            'topic': 14,
            'topic_position': 1,
            'post_time': datetime(2009, 12, 12, 14, 11, 37)
        }
        self.assertEqual(firstMessage, expectedFirstMessage)

        self.assertEqual(len(firstMessageContent['raw']), 1276)
        self.assertEqual(len(firstMessageContent['no_html']), 1208)
        self.assertEqual(len(firstMessageContent['no_quote']), 1276)
        self.assertEqual(len(firstMessageContent['no_quote_no_html']), 1208)

        f = codecs.open("{0}/example/topic_602041.12400.html".format(
            os.path.dirname(os.path.abspath(__file__))), 'r', 'utf-8')
        html = f.read()
        f.close()
        data = parseTopicPage(html)
        self.assertEqual(data['num_pages'], 621)
        self.assertEqual(
            data['messages'][0]['post_time'],
            datetime.combine(datetime.utcnow().date(), tm(21, 3, 11)))
        # print "Content of Message 1"
        # print data['messages'][0]['content']
        # print "Content of Message 1, No HTML"
        # print data['messages'][0]['content_no_html']
        # print "Content of Message 1, No Quote"
        # print data['messages'][0]['content_no_quote']
        # print "Content of Message 1, No Quote, No HTML"
        # print data['messages'][0]['content_no_quote_no_html']

if __name__ == "__main__":
    unittest.main()
