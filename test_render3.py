from renderer import render_pdf

plan = {
    "doc_type": "letter",
    "language": "en",
    "direction": "ltr",
    "title": "Formal Letter of Recommendation",
    "subtitle": None,
    "author": "Jane Smith, HR Director",
    "date": "July 2026",
    "needs_cover": False,
    "needs_toc": False,
    "content_markdown": """Dear Hiring Committee,

I am writing to enthusiastically recommend **John Doe** for the Senior Developer position at your organization.

## Professional Background
John worked with our team for over three years, consistently delivering high-quality software solutions.

## Key Strengths
- Strong problem-solving skills
- Excellent team collaboration
- Deep expertise in distributed systems

I am confident John will be a valuable addition to your team.

Sincerely,
Jane Smith
""",
}

render_pdf(plan, "test_letter.pdf")
print("done")
