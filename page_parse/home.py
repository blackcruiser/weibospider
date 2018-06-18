import re
import json
import urllib.parse

from bs4 import BeautifulSoup

from page_get import status
from logger import parser
from db.models import WeiboData
from db.models import WeiboPraise
from db.dao import PraiseOper
from config import get_crawling_mode
from decorators import parse_decorator


# weibo will use https in the whole website in the future,so the default protocol we use is https
ORIGIN = 'http'
PROTOCOL = 'https'
ROOT_URL = 'weibo.com'
CRAWLING_MODE = get_crawling_mode()


# todo 重构搜索解析代码和主页解析代码，使其可重用；捕获所有具体异常，而不是笼统的使用Exception
@parse_decorator('')
def get_weibo_infos_right(html):
    """
    通过网页获取用户主页右边部分（即微博部分）字符串
    :param html: 
    :return: 
    """
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all('script')
    pattern = re.compile(r'FM.view\((.*)\)')

    # 如果字符串'fl_menu'(举报或者帮上头条)这样的关键字出现在script中，则是微博数据区域
    cont = ''
    for script in scripts:
        m = pattern.search(script.string)
        if m and 'fl_menu' in script.string:
            all_info = m.group(1)
            cont += json.loads(all_info).get('html', '')
    return cont


@parse_decorator(None)
def get_weibo_forward_info_detail(mid, each, html):
    wb_data = WeiboData()

    if str(each).find('抱歉，此微博已被作者删除') != -1:
        wb_data.weibo_id = mid
        wb_data.is_delete = 1
        return wb_data, 0

    try:
        each = each.find(attrs={'node-type': 'feed_list_forwardContent'})
    except:
        return;
    try:
        user_cont = each.find(attrs={'class': 'WB_info'})
    except:
        return;

    try:
        user_info = str(user_cont.find('a'))
    except:
        return;

    user_pattern = 'id=(\\d+)&amp'
    m = re.search(user_pattern, user_info)
    if m:
        wb_data.uid = m.group(1)
    else:
        parser.warning("fail to get user'sid, the page source is{}".format(html))
        return None

    weibo_pattern = 'mid=(\\d+)'
    m = re.search(weibo_pattern, str(each))
    if m:
        wb_data.weibo_id = m.group(1)
    else:
        parser.warning("fail to get weibo's id,the page source {}".format(html))
        return None

    try:
        time_url = each.find(attrs={'node-type': 'feed_list_item_date'})
    except:
        pass

    wb_data.create_time = time_url.get('title', '')
    wb_data.weibo_url = time_url.get('href', '')
    if ROOT_URL not in wb_data.weibo_url:
        wb_data.weibo_url = '{}://{}{}'.format(PROTOCOL, ROOT_URL, wb_data.weibo_url)

    def url_filter(url):
        return ':'.join([PROTOCOL, url]) if PROTOCOL not in url and ORIGIN not in url else url

    try:
        full_imgs = each.find(attrs={'node-type': 'feed_list_media_prev'}).find(attrs={'node-type': 'fl_pic_list'})
        if full_imgs.has_attr('action-data'):
            url_param = full_imgs['action-data']
            full_imgs_url = urllib.parse.parse_qs(url_param)['clear_picSrc'][0]
            full_imgs_url_arr = full_imgs_url.split(',')
            for i, url in enumerate(full_imgs_url_arr):
                full_imgs_url_arr[i] = "https:" + url
            wb_data.weibo_img = ';'.join(full_imgs_url_arr)
    except Exception:
        wb_data.weibo_img = ''


    try:
        imgs = str(each.find(attrs={'node-type': 'feed_list_media_prev'}).
                   find_all('img'))
        imgs_url = map(url_filter, re.findall(r"src=\"(.+?)\"", imgs))
        wb_data.weibo_preview_img = ';'.join(imgs_url)
    except Exception:
        wb_data.weibo_preview_img = ''



    try:
        video = str(each.find(attrs={'node-type': 'feed_list_media_prev'}).
                   find_all('video'))
        video_url = map(url_filter, re.findall(r"src=\"(.+?)\"", video))
        wb_data.weibo_video = ';'.join(video_url)
    except Exception:
        wb_data.weibo_video = ''

    try:
        li = str(each.find(attrs={'node-type': 'feed_list_media_prev'}).
                 find_all('li'))
        extracted_url = urllib.parse.unquote(re.findall(r"video_src=(.+?)&amp;", li)[0])
        wb_data.weibo_video = url_filter(extracted_url)
    except Exception:
        wb_data.weibo_video = ''

    try:
        wb_data.weibo_cont = each.find(attrs={'node-type': 'feed_list_reason'}).text.strip()
    except Exception:
        wb_data.weibo_cont = ''

    if '展开全文' in str(each):
        is_all_cont = 0
    else:
        is_all_cont = 1

    try:
        wb_data.device = each.find(attrs={'class': 'WB_from S_txt2'}).find(attrs={'action-type': 'app_source'}).text
    except Exception:
        wb_data.device = ''

    try:
        wb_data.repost_num = int(each.find(attrs={'action-type': 'fl_forward'}).find_all('em')[1].text)
    except Exception:
        wb_data.repost_num = 0
    try:
        wb_data.comment_num = int(each.find(attrs={'action-type': 'fl_comment'}).find_all('em')[1].text)
    except Exception:
        wb_data.comment_num = 0
    try:
        wb_data.praise_num = int(each.find(attrs={'action-type': 'fl_like'}).find_all('em')[1].text)
    except Exception:
        wb_data.praise_num = 0

    return wb_data, is_all_cont


@parse_decorator(None)
def get_weibo_info_detail(each, html):

    wb_data = WeiboData()

    user_cont = each.find(attrs={'class': 'face'})
    user_info = str(user_cont.find('a'))
    user_pattern = 'id=(\\d+)&amp'
    m = re.search(user_pattern, user_info)
    if m:
        wb_data.uid = m.group(1)
    else:
        parser.warning("fail to get user'sid, the page source is{}".format(html))
        return None


    mid =each['mid']
    weibo_pattern = 'mid=(\\d+)'
    m = re.search(weibo_pattern, str(each))
    if m:
        wb_data.weibo_id = m.group(1)
    else:
        parser.warning("fail to get weibo's id,the page source {}".format(html))
        return None


    if each.has_attr('omid'):
        omid = each['omid']
        wb_data.is_origin = 0
        wb_data.weibo_forward_id = omid

    time_url = each.find(attrs={'node-type': 'feed_list_item_date'})
    wb_data.create_time = time_url.get('title', '')
    wb_data.weibo_url = time_url.get('href', '')
    if ROOT_URL not in wb_data.weibo_url:
        wb_data.weibo_url = '{}://{}{}'.format(PROTOCOL, ROOT_URL, wb_data.weibo_url)

    def url_filter(url):
        return ':'.join([PROTOCOL, url]) if PROTOCOL not in url and ORIGIN not in url else url

    try:
        full_imgs = each.find(attrs={'node-type': 'feed_list_media_prev'}).find(attrs={'node-type': 'fl_pic_list'})
        if full_imgs.has_attr('action-data'):
            url_param = full_imgs['action-data']
            full_imgs_url = urllib.parse.parse_qs(url_param)['clear_picSrc'][0]
            full_imgs_url_arr = full_imgs_url.split(',')
            for i, url in enumerate(full_imgs_url_arr):
                full_imgs_url_arr[i] = "https:" + url
            wb_data.weibo_img = ';'.join(full_imgs_url_arr)
    except Exception:
        wb_data.weibo_img = ''

    try:
        imgs = str(each.find(attrs={'node-type': 'feed_content'}).find(attrs={'node-type': 'feed_list_media_prev'}).
                   find_all('img'))
        imgs_url = map(url_filter, re.findall(r"src=\"(.+?)\"", imgs))
        wb_data.weibo_preview_img = ';'.join(imgs_url)
    except Exception:
        wb_data.weibo_preview_img = ''

    try:
        li = str(each.find(attrs={'node-type': 'feed_content'}).find(attrs={'node-type': 'feed_list_media_prev'}).
                 find_all('li'))
        extracted_url = urllib.parse.unquote(re.findall(r"video_src=(.+?)&amp;", li)[0])
        wb_data.weibo_video = url_filter(extracted_url)
    except Exception:
        wb_data.weibo_video = ''

    try:
        wb_data.weibo_cont = each.find(attrs={'node-type': 'feed_content'}).find(
            attrs={'node-type': 'feed_list_content'}).text.strip()
    except Exception:
        wb_data.weibo_cont = ''

    if '展开全文' in str(each):
        is_all_cont = 0
    else:
        is_all_cont = 1

    try:
        wb_data.device = each.find(attrs={'class': 'WB_from S_txt2'}).find(attrs={'action-type': 'app_source'}).text
    except Exception:
        wb_data.device = ''

    try:
        wb_data.repost_num = int(each.find(attrs={'action-type': 'fl_forward'}).find_all('em')[1].text)
    except Exception:
        wb_data.repost_num = 0
    try:
        wb_data.comment_num = int(each.find(attrs={'action-type': 'fl_comment'}).find_all('em')[1].text)
    except Exception:
        wb_data.comment_num = 0
    try:
        wb_data.praise_num = int(each.find(attrs={'action-type': 'fl_like'}).find_all('em')[1].text)
    except Exception:
        wb_data.praise_num = 0

    praise = each.find(attrs={'suda-uatrack': "key=tblog_profile_v6&value=like_title"})
    if praise:
        praise_m = re.search("weibo.com/(\d+)/like", praise['href'])
        if praise_m:
            uid = praise_m.group(1)
            wb_praise = WeiboPraise()
            wb_praise.user_id = uid
            wb_praise.weibo_id = wb_data.weibo_id
            PraiseOper.add_one(wb_praise)
    return wb_data, is_all_cont


def get_weibo_list(html):
    """
    get the list of weibo info
    :param html:
    :return: 
    """
    if not html:
        return list()
    soup = BeautifulSoup(html, "html.parser")
    feed_list = soup.find_all(attrs={'action-type': 'feed_list_item'})
    weibo_datas = []
    for data in feed_list:
        r = get_weibo_info_detail(data, html)
        if r is not None:
            wb_data = r[0]
            if r[1] == 0 and CRAWLING_MODE == 'accurate':
                weibo_cont = status.get_cont_of_weibo(wb_data.weibo_id)
                wb_data.weibo_cont = weibo_cont if weibo_cont else wb_data.weibo_cont
            weibo_datas.append(wb_data)

            if wb_data.is_origin == 0:
                fr = get_weibo_forward_info_detail(wb_data.weibo_forward_id, data, html)
                if fr is not None:
                    wb_fd_data = fr[0]
                    if fr[1] == 0 and CRAWLING_MODE == 'accurate':
                        weibo_fd_cont = status.get_cont_of_weibo(wb_fd_data.weibo_id)
                        wb_fd_data.weibo_cont = weibo_fd_cont if weibo_fd_cont else wb_fd_data.weibo_cont
                    weibo_datas.append(wb_fd_data)

    return weibo_datas


@parse_decorator(1)
def get_max_num(html):
    """
    get the total page number
    :param html:
    :return:
    """
    soup = BeautifulSoup(html, "html.parser")
    href_list = soup.find(attrs={'action-type': 'feed_list_page_morelist'}).find_all('a')
    return len(href_list)


@parse_decorator(list())
def get_data(html):
    """
    从主页获取具体的微博数据
    :param html: 
    :return: 
    """
    cont = get_weibo_infos_right(html)
    return get_weibo_list(cont)


@parse_decorator(list())
def get_ajax_data(html):
    """
    通过返回的ajax内容获取用户微博信息
    :param html: 
    :return: 
    """
    cont = json.loads(html, encoding='utf-8').get('data', '')
    return get_weibo_list(cont)


@parse_decorator(1)
def get_total_page(html):
    """
    从ajax返回的内容获取用户主页的所有能看到的页数
    :param html: 
    :return: 
    """
    cont = json.loads(html, encoding='utf-8').get('data', '')
    if not cont:
        # todo 返回1或者0还需要验证只有一页的情况
        return 1
    return get_max_num(cont)
