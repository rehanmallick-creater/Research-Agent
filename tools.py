
from tavily import TavilyClient 
from langchain.tools import tool 
import requests 
import os 
from bs4 import BeautifulSoup 
from rich import print 
from dotenv import load_dotenv 
load_dotenv() 

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")) 

@tool 
def web_search(query: str)-> str:
    """Search the web for recent and reliable information on a topic . Returns Titles , URLs and snippets.""" 
    results =tavily.search(query=query, max_results=5)

    out =[]

    for r in results['results']:
        out.append(
            f"Title: {r['title']}\nURL: {r['url']}\nSnippet:{r['content'][:300]}\n"
        )

    return "\n----\n".join(out)


@tool
def scrape_url(url: str)-> str:
    """Scrape and return clear text content from a given URL for deeplearning reading.""" 
    try:
        resp=requests.get(url, timeout=8 , headers={"User-Agent": "Mozilla/5,0"})
        soup =BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script","style", "nav", "footer"]):
            tag.decompose()

        return soup.get_text(seperator=" ", strip=True)[:3000]

    except Exception as e:
        return f"could not scrape URL: {str(e)}"