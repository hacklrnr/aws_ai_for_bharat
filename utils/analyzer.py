import os
import json
import boto3
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1")
)


def invoke_nova(prompt: str, max_tokens: int = 1000, temperature: float = 0.8) -> str:
    body = json.dumps({
        "messages": [
            {"role": "user", "content": [{"text": prompt}]}
        ],
        "inferenceConfig": {
            "max_new_tokens": max_tokens,
            "temperature": temperature
        }
    })
    response = bedrock.invoke_model(
        modelId="amazon.nova-lite-v1:0",
        body=body
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


@retry(wait=wait_exponential(multiplier=2, min=10, max=60), stop=stop_after_attempt(3))
def perform_gap_analysis(summaries, topic):
    context_text = "\n\n".join([f"SOURCE: {s['title']}\n{s['content']}" for s in summaries])

    prompt = f"""
You are a content strategy expert helping a writer craft a unique and impactful blog post.

You have been given summaries of the top existing articles on the topic: '{topic}'.

RESEARCH SUMMARIES:
{context_text}

Your task is to produce a structured WRITING GUIDE for the user. Do NOT write the article itself.

Structure your response exactly as follows:

## What Everyone Is Already Saying
- List 3-4 angles, arguments, or framings that appear repeatedly across the existing articles.
- These are the angles the user should AVOID to prevent being repetitive.

## The Gaps Nobody Is Covering
- List 3-4 specific perspectives, angles, or questions that are completely missing from the existing content.
- Focus on technical, ethical, human-interest, or future-facing blind spots.

## Questions Worth Exploring
- List 3-4 thought-provoking or contrarian questions the user could build their article around.
- These should challenge assumptions made in the existing articles.

## Recommended Angles for a Standout Blog Post
- List 3-4 concrete, specific angles the user could take to write something genuinely differentiated.
- Each angle should be actionable — something the user can sit down and write about immediately.

## Suggested Article Structure
- Provide a simple outline (intro, 3-4 sections, conclusion) tailored to the most promising angle above.

Keep the tone practical and direct. This is a guide for a writer, not a report for an executive.
"""

    return invoke_nova(prompt, max_tokens=1200, temperature=0.8)