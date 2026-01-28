# import json
# import openai
# def img_format_response(raw_result):
#     """
#     Uses GPT-4o-mini to convert internal results into
#     friendly WhatsApp-ready replies.
#     """

#     # Convert raw result to text safely
#     if isinstance(raw_result, dict):
#         raw_text = raw_result.get("message") or json.dumps(raw_result, indent=2)
#     else:
#         raw_text = str(raw_result)

#     system_prompt = (
#         "You are a text rewriter for WhatsApp messages.\n"
#         "Your job is to rewrite the given content to be friendly, clear, and easy to read on WhatsApp.\n\n"
#         "STRICT RULES:\n"
#         "- DO NOT add any new information or knowledge\n"
#         "- DO NOT remove any factual information\n"
#         "- DO NOT infer, explain, or interpret\n"
#         "- DO NOT add causes, meanings, or advice\n"
#         "- DO NOT add follow-up questions unless already present\n"
#         "- Keep the meaning EXACTLY the same as the input\n"
#         "- You may rephrase sentences for clarity\n"
#         "- You may improve formatting (line breaks, bullets)\n"
#         "- You may add at most 1–2 emojis if appropriate\n"
#         "- DO NOT return JSON\n"
#     )


#     user_prompt = f"""
#     Content to rewrite:
#     \"\"\"
#     {raw_text}
#     \"\"\"
#     """

#     response = openai.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         temperature=0.2,
#         max_tokens=3000,
#     )

#     return response.choices[0].message.content.strip()
