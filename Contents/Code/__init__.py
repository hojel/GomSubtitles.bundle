import urllib, unicodedata
import os
import copy

BASE_URL   = "http://gom.gomtv.com"
SRCH_KEY_URL = BASE_URL+"/jmdb/search.html?key=%s"
SRCH_VAL_URL = BASE_URL+"/main/index.html?ch=subtitles&pt=l&menu=subtitles&lang=0&sValue=%s"
JAMAK_URL    = BASE_URL+"/main/index.html?ch=subtitles&pt=v&menu=subtitles&seq=%s"
DOWN_URL     = BASE_URL+"/main/index.html?pt=down&ch=subtitles&intSeq=%s&capSeq=%s"

RE_REDIR_LOC = Regex("= *'([^']*)';")
RE_SUB_TITLE = Regex("<h4>([^<]*)</h4>")
RE_SUB_ID = Regex('name="intseq" +value="(\d+)"')
RE_JAMAK_DOWN = Regex('a href="(jamak://gom.gomtv.com.*?)"')
RE_JAMAK_DOWN2 = Regex("downJm\('(.*?)', *'(.*?)', *'(.*?)'\);")

mediaCopies = {}    # idea from PodnapisiSubtitles.bundle
 
def Start():
  HTTP.CacheTime = 0
  HTTP.Headers['User-Agent'] = 'GomPlayer 2, 1, 23, 5007 (KOR)'

def movieSearch(meta, lang, part):
  # search with hash key generated from file
  filename = unicodedata.normalize('NFKC', unicode(os.path.basename(part.file))).strip()
  Log.Debug("filename: " + filename)
  items = searchSubtitlesWithFile(filename)

  if len(items) == 0:
    # search with file name
    items = searchSubtitles( SRCH_VAL_URL % filename )

  if len(items) > 0:
    sub_id = items[0].id    # select the first candidate
    fetchSubtitles(sub_id, lang, part)

def tvSearch(meta, lang, part):
  # search with hash key generated from file
  filename = unicodedata.normalize('NFKC', unicode(os.path.basename(part.file))).strip()
  Log.Debug("filename: " + filename)
  items = searchSubtitlesWithFile(filename)

  if len(items) == 0:
    # search with file name
    items = searchSubtitles( SRCH_VAL_URL % filename )

  if len(items) > 0:
    sub_id = items[0].id    # select the first candidate
    fetchSubtitles(sub_id, lang, part)

def searchSubtitlesWithFile(filename):
  # Limited to support due to safety issue
  #   http://forums.plexapp.com/index.php/topic/36260-open-media-file-from-python/
  return []

  buff = Core.storage.load(filename, 1024*1024)
  key = Hash.MD5(buff)
  return searchSubtitles(SRCH_KEY_URL % key)

def searchSubtitles(url):
  page = HTTP.Request(url).content

  if 'search_failed_smi' in page:
    return []
  elif "<script>location.href" in page or "<script>top.location.replace" in page:
    url = RE_REDIR_LOC(page).group(1)
    Log.Debug("redirected to "% url)
    page = HTTP.Request(url).content
    id = RE_SUB_ID.search(page).group(1)
    title = RE_SUB_TITLE.search(page).group(1)
    return [ MetadataSearchResult(id = id, name = title, score = 100) ]

  # items from result page
  html = HTML.ElementFromString(page)
  subtitles = []
  score = 99
  for row in html.xpath('//table[@class="tbl_lst"]//tbody/tr'):
    a_node = row.xpath('.//a')[0]
    #url = BASE_URL + a_node.get('href')
    title = a_node.text
    sub_id = row.xpath('.//span[@class="txt_clr1"]')[0].text
    lang_str = row.xpath('.//span[@class="txt_clr3"]')[0].text
    Log.Debug(u"result: %s %s %s" % (title, sub_id, lang_str))
    
    if u"한글" == lang_str:
      lang = "ko"
    elif u"영문" == lang_str:
      lang = "en"
    else:   # [통합]
      lang = "ko"
    subtitles.append( MetadataSearchResult(id = sub_id, name = title, lang = lang, score = score) )
    score = score - 1

  return subtitles

def fetchSubtitles(sub_id, lang, part):
  url = JAMAK_URL % sub_id

  page = HTTP.Request(url).content

  match = RE_JAMAK_DOWN.search(page)
  if match:
    url = match.group(1)
    subData = HTTP.Request(url).content
  else:
    match = RE_JAMAK_DOWN2.search(page)
    if match:
      url = DOWN_URL % match.group(1, 2)
      subData = HTTP.Request(url).content
    else:
      Log.Info('No subtitles available for language ' + lang)
      return

  subFmt = 'smi'
  subEncoding = chdet(subData)
  if subEncoding != 'Unknown':
    Log('transcode to cp949')
    subData = unicode(subData, subEncoding, 'ignore').encode('cp949')

  part.subtitles[Locale.Language.Match(lang)][url] = Proxy.Media(subData, ext=subFmt)
  Log.Info('Subtitles downloaded for language ' + lang)

def chdet(aBuf):
    # If the data starts with BOM, we know it is UTF
  if aBuf[:3] == '\xEF\xBB\xBF':
    # EF BB BF  UTF-8 with BOM
    result = "UTF-8"
  elif aBuf[:2] == '\xFF\xFE':
    # FF FE  UTF-16, little endian BOM
    result = "UTF-16LE"
  elif aBuf[:2] == '\xFE\xFF':
    # FE FF  UTF-16, big endian BOM
    result = "UTF-16BE"
  elif aBuf[:4] == '\xFF\xFE\x00\x00':
    # FF FE 00 00  UTF-32, little-endian BOM
    result = "UTF-32LE"
  elif aBuf[:4] == '\x00\x00\xFE\xFF': 
    # 00 00 FE FF  UTF-32, big-endian BOM
    result = "UTF-32BE"
  elif aBuf[:4] == '\xFE\xFF\x00\x00':
    # FE FF 00 00  UCS-4, unusual octet order BOM (3412)
    result = "X-ISO-10646-UCS-4-3412"
  elif aBuf[:4] == '\x00\x00\xFF\xFE':
    # 00 00 FF FE  UCS-4, unusual octet order BOM (2143)
    result = "X-ISO-10646-UCS-4-2143"
  else:
    result = "Unknown"
  return result

# entry for Movie
class GomSubtitlesAgentMovies(Agent.Movies):
  name = 'GomTV Subtitles'
  languages = [Locale.Language.Korean, Locale.Language.English]
  primary_provider = False
  
  def search(self, results, media, lang):
    mediaCopy = copy.copy(media.primary_metadata)
    uuid = String.UUID()
    mediaCopies[uuid] = mediaCopy
    results.Append(MetadataSearchResult(id = uuid, score = 100, lang = lang))
  
  def update(self, metadata, media, lang):
    mc = mediaCopies[metadata.id]

    for i in media.items:
      for part in i.parts:
        movieSearch(mc, lang, part)

    del(mediaCopies[metadata.id])

# entry for TV shows
class GomSubtitlesAgentTV(Agent.TV_Shows):
  name = 'GomTV Subtitles'
  languages = [Locale.Language.Korean, Locale.Language.English]
  primary_provider = False

  def search(self, results, media, lang):
    mediaCopy = copy.copy(media.primary_metadata)
    uuid = String.UUID()
    mediaCopies[uuid] = mediaCopy
    results.Append(MetadataSearchResult(id = uuid, score = 100, lang = lang))

  def update(self, metadata, media, lang):
    mc = mediaCopies[metadata.id]

    for s in media.seasons:
      # just like in the Local Media Agent, if we have a date-based season skip for now.
      if int(s) < 1900:
        for e in media.seasons[s].episodes:
          for i in media.seasons[s].episodes[e].items:
            for part in i.parts:
              tvSearch(mc, lang, part)

    del(mediaCopies[metadata.id])

# end
