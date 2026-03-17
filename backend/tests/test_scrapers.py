from app.scraper.apify_linkedin import build_linkedin_run_inputs, posting_from_linkedin_item
from app.scraper.common import dedupe_listings, parse_posted_at
from app.scraper.djinni import parse_jobposting_scripts
from app.scraper.hn_jobs import build_hn_comment_url


def test_parse_posted_at_supports_iso_dates() -> None:
    parsed = parse_posted_at("2026-03-17")

    assert parsed is not None
    assert parsed.isoformat() == "2026-03-17T00:00:00+00:00"


def test_dedupe_listings_preserves_first_occurrence() -> None:
    listings = [
        ("https://example.com/jobs/1", "Role A", "Acme", None),
        ("https://example.com/jobs/1", "Role A duplicate", "Acme", None),
        ("https://example.com/jobs/2", "Role B", "Beta", None),
    ]

    deduped = dedupe_listings(listings)

    assert deduped == [
        ("https://example.com/jobs/1", "Role A", "Acme", None),
        ("https://example.com/jobs/2", "Role B", "Beta", None),
    ]


def test_build_linkedin_run_inputs_generates_one_payload_per_title() -> None:
    payloads = build_linkedin_run_inputs(
        titles_csv="Python AI Engineer,ML Engineer",
        location="Europe",
        date_posted="r604800",
        limit_per_title=15,
        company_names_csv="OpenAI,Anthropic",
        remote_codes_csv="2,3",
    )

    assert payloads == [
        {
            "title": "Python AI Engineer",
            "location": "Europe",
            "datePosted": "r604800",
            "companyName": ["OpenAI", "Anthropic"],
            "remote": ["2", "3"],
            "maxItems": 15,
        },
        {
            "title": "ML Engineer",
            "location": "Europe",
            "datePosted": "r604800",
            "companyName": ["OpenAI", "Anthropic"],
            "remote": ["2", "3"],
            "maxItems": 15,
        },
    ]


def test_posting_from_linkedin_item_maps_job_payload() -> None:
    posting = posting_from_linkedin_item(
        {
            "jobUrl": "https://www.linkedin.com/jobs/view/123",
            "title": "Senior ML Engineer",
            "companyName": "Example AI",
            "descriptionText": "Python, FastAPI, RAG",
            "postedDate": "2026-03-16",
        }
    )

    assert posting is not None
    assert posting.url == "https://www.linkedin.com/jobs/view/123"
    assert posting.company == "Example AI"
    assert posting.source == "LinkedIn"
    assert posting.source_group == "Global"
    assert posting.posted_at is not None
    assert posting.posted_at.isoformat() == "2026-03-16T00:00:00+00:00"


def test_build_hn_comment_url_uses_comment_anchor() -> None:
    assert (
        build_hn_comment_url("42306918", "4321")
        == "https://news.ycombinator.com/item?id=42306918#4321"
    )


def test_parse_jobposting_scripts_reads_djinni_json_ld() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          [
            {
              "@context": "https://schema.org/",
              "@type": "JobPosting",
              "title": "Senior Python Engineer",
              "url": "https://djinni.co/jobs/801646-senior-python-engineer/",
              "datePosted": "2026-03-17T12:34:20.842738",
              "hiringOrganization": {"@type": "Organization", "name": "GlobalLogic"}
            }
          ]
        </script>
      </head>
    </html>
    """

    listings = parse_jobposting_scripts(html)

    assert len(listings) == 1
    url, title, company, posted_at = listings[0]
    assert url == "https://djinni.co/jobs/801646-senior-python-engineer/"
    assert title == "Senior Python Engineer"
    assert company == "GlobalLogic"
    assert posted_at is not None
    assert posted_at.isoformat() == "2026-03-17T12:34:20.842738+00:00"
