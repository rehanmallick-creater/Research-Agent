import time

from agent import build_reader_agent, build_search_agent, write_chain, critic_chain


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

    search_agent = build_search_agent()
    search_result = invoke_with_retry(lambda: search_agent.invoke({
        "messages": [("user", f"Find recent, reliable and detailed information about: {topic}")]
    }))
    state["search_results"] = search_result["messages"][-1].content
    print("\n search result ", state["search_results"])
    emit("step", {"step": 1, "status": "done", "output": str(state["search_results"])})

    # Step 2 - reader agent
    print("\n" + "=" * 50)
    print("step 2 - Reader agent is scraping top resources ...")
    print("=" * 50)
    emit("step", {"step": 2, "status": "running", "label": "Reader agent is scraping top resources"})

    reader_agent = build_reader_agent()
    reader_result = invoke_with_retry(lambda: reader_agent.invoke({
        "messages": [(
            "user",
            f"Based on the following search results about '{topic}', "
            f"pick the most relevant URL and scrape it for deeper content.\n\n"
            f"Search Results:\n{str(state['search_results'])[:800]}"
        )]
    }))
    state["scraped_content"] = reader_result["messages"][-1].content
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