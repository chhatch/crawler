import sys
import re
import json
import codecs
import urllib.parse
import urllib.request
from googleSheets import getAccessToken, sheetValues, moveLinkToComplete
from time import time, sleep
from multiprocessing import Process, Queue, freeze_support
from lxml import html
from lxml import _elementpath
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngine import *
from PyQt5.QtWebEngineWidgets import *

#python setup.py build
#use chcp 65001 in command prompt
# this regular expression matches phones number in the following formats:
# (123) 456-7890, (123) 456.7890, 123-456-7890, and 123.456.7890
phoneReg = re.compile('((?:\()?\d{3}(?:-|\.| |\) )\d{3}(?:-|\.)\d{4})') #the period is a wildcard! Escape dat junt
emailReg = re.compile('[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}')
linkReg = re.compile('(?P<url>https?://[\'\"\<>#%{}|\\\^\~\[\]`\s]+)')
forbiddenDomains = ["facebook.com", "instagram.com", "pinterest.com", "linkedin.com", "twitter.com", "google.com", 'itunes.apple.com', "youtube.com", "hammernutrition.com", 'wholefoodsmarket.com', 'myvega.com', 'lornajane.com']
forbiddinEmail = ['@illuminatistudios.com']
forbiddenExtensions = ['.png', '.jpg', '.gif', '.svg', 'aspx']
accessToken = {'token': '',
               'expires': 0}
aeMarket = '1M5CLqzJO4QQgrOiGZKCINcYB1WE39ByoZ2Rr-8WGIXw'
timeToAbort = 30
waitForLoad = 0
app = QApplication(sys.argv)

#class fakeOut (object):
   # def __init__(self, *args, **kwargs):
   #     pass
   ## def flush():
    #    pass
    #def write(dummy):
    #    pass
#sys.stdout = fakeOut
#sys.stderr = fakeOut
class LinkScrubber(object):
    def __init__(self, *args, **kwargs):
        pass

    def run(self, url, depth, q):        
        p = Process(target=self.render, args=(url, depth, q))
        processStart = time()
        p.start()
        self.data = []
        while p.is_alive():
            timeElapsed = time() - processStart            
            if timeElapsed > timeToAbort:
                print('Process has timed out. Aborting')
                p.terminate()
                app.quit() #maybe this isn't killing the same instance of Qapp as the thread, remember spawning a new process pretty much just starts the program again.
            else:   
                if not q.empty():          
                    self.data.append(q.get())             
        p.join()

    def render(self, url, depth, q):
        self.q = q
        self.url = url
        self.depth = depth
        QWebEngineProfile.defaultProfile().setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36")
        self.qt = QWebEnginePage()
        #self.qt.loadStarted.connect(self._loadStarted)
        #self.qt.loadProgress.connect(self._loadProgress)
        self.qt.loadFinished.connect(self._loadFinished)
        self.qt.load(QUrl(url))
        app.exec_()

    #def _loadStarted(self):
       # print ('Load started.')

   # def _loadProgress(self, progress):
       # print ('Loading progress: ' + str(progress) + '%')

    def _loadFinished(self, result):
        #print ('Load finished.')
        if self.depth == 0:
            sleep(waitForLoad)
        self.qt.toHtml(self.callable)

    def callable(self, data):
        self.html = data
        data = html.fromstring(data.encode())
        links = []
        txtLinks = []        
        els = data.xpath('//a')
        for el in els:
            url = el.xpath("./@href") #the '.' indicates a local search
            title =  el.xpath("./text()")
            if len(url) == 0:
                continue
            url[0] = urllib.parse.urljoin(self.url, url[0])
            print(url[0])            
            links.append({'url': url[0], 'title': title[0] if len(title) > 0 else 'Link title not found'})  
        txtLinks = linkReg.findall(self.html) #catches urls in in html links
        for link in txtLinks:
            link = link.rstrip('\'"')
            links.append({'url': link, 'title': 'Link found in text..'})
            print('TEXT LINK ' + link)            
        emails = emailReg.findall(self.html)  ##get email addresses
        numbers = phoneReg.findall(self.html)   ##get phone numbers
        for link in links:
            link['url'] = link['url'].strip() #remove trailing and leading spaces!!        
            self.q.put(['link', link])        
        for email in emails:
            if not any(ext in email for ext in forbiddenExtensions):
                    self.q.put(['email', email])
        for number in numbers:
            self.q.put(['number', number])
        app.quit()

class LinkCrawler(object):

        def __init__(self, link, depth, depthLimit, q, **kwargs):
            print(depth)
            self.url = link['url']
            self.title = link['title']
            self.depth = depth
            self.depthLimit = depthLimit
            self.linkData = self.getLinkData()
            self.allLinks = []
            self.emails = []
            self.numbers = []
            self.sortData()
            print ('Links found: ' + str(len(self.allLinks)))
            print ('Email addresses found: ' + str(len(self.emails)))
            for email in self.emails:
                print(email)
            self.validLinks = []
            self.invalidLinks = []
            self.verifyLinks()
            #for link in self.validLinks:
               # print(link['url'])
            self.children = []
            self.spawnChildren()
            pass

        def getLinkData(self):
            l = LinkScrubber()
            l.run(self.url, self.depth, q)          
            return l.data         
            
        def sortData(self):            
            def isLink(link):
                if link['url'] not in allLinks  or self.depth == 0:                    
                    self.allLinks.append(link)                    
                    allLinks.append(link['url'])
            def isEmail(email):
                if email not in allEmails:
                    self.emails.append(email)
                    allEmails.append(email)
            def isNumber(number):
                if number not in allNumbers:
                    self.numbers.append(number)
                    allNumbers.append(number)                    
            dataType = {'link': isLink, 'email': isEmail, 'number': isNumber}                 
            for datum in self.linkData:
                dataType[datum[0]](datum[1]) 

        def verifyLinks(self):
            for link in self.allLinks:           
                if any(domain in link['url'] for domain in forbiddenDomains):
                    self.invalidLinks.append(link)
                elif QUrl(link['url']).isValid():
                    self.validLinks.append(link)
                else:
                    self.invalidLinks.append(link) 

        def spawnChildren(self):
            if self.depth < self.depthLimit:
                for link in self.validLinks:
                    if link['url'] not in linksVisited:            
                        print('Visiting: ' + link['title'] + '\n' + link['url'] + '\n')
                        self.children.append(LinkCrawler(link, self.depth + 1, self.depthLimit, q))
            else:
                print('Depth limit reached.\n') 
    
def getAllData(branch, key):    
    if len(branch.emails) > 0 or len(branch.numbers):    
        dataDict[key].append([branch.title, branch.url, branch.emails, branch.numbers])     
   #data = {
       #timedOut: false,
       #hasChildren: true,
       #depth: 0,
       #loadTime: int,
       #totalTime: number,
       #allLinks: [links from self and all children],
       #allEmails: [email addresses from self and all children],
       #emails: [emails from self],
       #links: [immediate child links],
       #"immediate child link 1": same structure as whole
       #}     
def traverse(branch, key):      
    for twig in branch.children:        
        traverse(twig, key)    
    getAllData(branch, key)  
    
if __name__ == '__main__':
    freeze_support() #necessary in order to properly freeze file
    emailSource = '1'#'Links to Crawl'
    linkDump = '2'#'Email Addresses Found'
    linksVisited = ''
    allLinks = []  #this is used to record a link only once if it appears severals times on a single page
    allEmails = []
    allNumbers = []
    q = Queue(maxsize=0)
    accessToken = getAccessToken(accessToken)
    crawl = True
    while crawl:
        linkData = sheetValues(aeMarket, emailSource, 'A2:B', None, {}, None, 'GET', accessToken) #sheet values are returned as 2d array
        if 'values' in linkData.keys():
            linkArray = linkData['values']
            link = {}
            link['url'] = linkData['values'][0][0]
            link['depthLimit'] = int(linkData['values'][0][1]) if len(linkData['values'][0]) == 2 else 2
            link['title'] = 'Base'
        else:
            print('No links to crawl')
            exit()
        emails = []
        dataDict = {}
        print('Starting at: ' + link['url'])
        linkTree = LinkCrawler(link, 0, link['depthLimit'], q)
        dataDict[link['url']] = []
        traverse(linkTree, link['url'])
        link['data'] = dataDict
        for key in dataDict:
            for page in dataDict[key]:
                emails.extend(page[2])
        accessToken = getAccessToken(accessToken)
        headers = {"Content-Type": "application/json"}
        currentEmailData = sheetValues(aeMarket, linkDump, 'A2:A', None, {}, None, 'GET', accessToken)
        if 'values' in currentEmailData.keys():
            currentEmails = currentEmailData['values']
            for email in currentEmails:
                print(email[0])
                emails.append(email[0])
            for email in emails:
                print(email)
        else:
            print('No email addresses in list')
        body = {'values': [emails], 'majorDimension': 'COLUMNS'}
        response = sheetValues(aeMarket, linkDump, 'A2:A' + str(len(emails) + 1), body, headers, {'valueInputOption': 'RAW'}, 'PUT', accessToken)
        print(response)
        moveLinkToComplete(link, aeMarket, emailSource, accessToken)