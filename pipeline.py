import re
import time

import tools
from agent import build_reader_agent, build_search_agent, write_chain, critic_chain

# Works whether you renamed the search tool to search_the_web or kept web_search
search_tool = getattr(tools, "search_the_web", None) or tools.web_search
scrape_tool = tools.scrape_url


def search_directly(topic):
    """Backup for step 1: call the search tool ourselves, no LLM tool-calling needed."""
    return search_tool.invoke({"query": topic})


def scrape_directly(search_text):
    """Backup for step 2: find URLs in the search results and scrape the first one that works."""
    urls = re.findall(r"https?://[^\s)\]>\"']+", search_text)
    for url in urls[:3]:
        content = scrape_tool.invoke({"url": url})
        if not content.startswith("could not scrape"):
            return f"Source: {url}\n\n{content}"
    return "No page could be scraped. Use the search results only."


def invoke_with_retry(call, tries=3):
    """Run call(). If the model makes a bad tool call, wait 2 seconds and try again."""
    for attempt in range(tries):
        try:
            return call()
        except Exception as error:
            if attempt == tries - 1:
                raise  # out of tries: show the real error
            print(f"Attempt {attempt + 1} failed ({error}). Retrying...")
            time.sleep(2)


def run_research_pipeline(topic: str, on_event=None) -> dict:
    """Runs the 4-step pipeline.

    on_event(event: str, data: dict) is optional; the FastAPI server uses it to
    stream progress to the browser. The CLI works exactly as before without it.
    """

    def emit(event: str, data: dict):
        if on_event:
            on_event(event, data)

    state = {}

    # Step 1 - search agent
    print("\n" + "=" * 50)
    print("step 1 - search agent is working ...")
    print("=" * 50)
    emit("step", {"step": 1, "status": "running", "label": "Search agent is working"})

    try:
        search_agent = build_search_agent()
        search_result = invoke_with_retry(lambda: search_agent.invoke({
            "messages": [("user", f"Find recent, reliable and detailed information about: {topic}")]
        }), tries=2)
        state["search_results"] = search_result["messages"][-1].content
    except Exception as error:
        print(f"Search agent failed ({error}). Searching directly instead.")
        state["search_results"] = search_directly(topic)
    print("\n search result ", state["search_results"])
    emit("step", {"step": 1, "status": "done", "output": str(state["search_results"])})

    # Step 2 - reader agent
    print("\n" + "=" * 50)
    print("step 2 - Reader agent is scraping top resources ...")
    print("=" * 50)
    emit("step", {"step": 2, "status": "running", "label": "Reader agent is scraping top resources"})

    try:
        reader_agent = build_reader_agent()
        reader_result = invoke_with_retry(lambda: reader_agent.invoke({
            "messages": [(
                "user",
                f"Based on the following search results about '{topic}', "
                f"pick the most relevant URL and scrape it for deeper content.\n\n"
                f"Search Results:\n{str(state['search_results'])[:800]}"
            )]
        }), tries=2)
        state["scraped_content"] = reader_result["messages"][-1].content
    except Exception as error:
        print(f"Reader agent failed ({error}). Scraping directly instead.")
        state["scraped_content"] = scrape_directly(str(state["search_results"]))
    print("\nscraped content: \n", state["scraped_content"])
    emit("step", {"step": 2, "status": "done", "output": str(state["scraped_content"])})

    # Step 3 - writer chain
    print("\n" + "=" * 50)
    print("step 3 - Writer is drafting the report ...")
    print("=" * 50)
    emit("step", {"step": 3, "status": "running", "label": "Writer is drafting the report"})

    research_combined = (
        f"SEARCH RESULTS: \n {state['search_results']} \n\n"
        f"DETAILED SCRAPED CONTENT : \n {state['scraped_content']}"
    )
    state["report"] = write_chain.invoke({
        "topic": topic,
        "research": research_combined,
    })
    print("\n Final Report\n", state["report"])
    emit("step", {"step": 3, "status": "done", "output": str(state["report"])})

    # Step 4 - critic
    print("\n" + "=" * 50)
    print("step 4 - critic is reviewing the report ")
    print("=" * 50)
    emit("step", {"step": 4, "status": "running", "label": "Critic is reviewing the report"})

    state["feedback"] = critic_chain.invoke({"report": state["report"]})
    print("\n critic report \n", state["feedback"])
    emit("step", {"step": 4, "status": "done", "output": str(state["feedback"])})

    return state


if __name__ == "__main__":
    topic = input("\n Enter a research topic : ")
    run_research_pipeline(topic)