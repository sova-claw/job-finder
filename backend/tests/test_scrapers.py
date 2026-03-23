from app.models.company import CompanySnapshot
from app.scraper.apify_linkedin import build_linkedin_run_inputs, posting_from_linkedin_item
from app.scraper.bigco import COMPANIES_TARGET, _build_company_targets, _parse_wix_listings
from app.scraper.careers_page import parse_ashby_jobs, parse_greenhouse_jobs, parse_lever_jobs
from app.scraper.common import dedupe_listings, parse_posted_at
from app.scraper.djinni import parse_jobposting_scripts
from app.scraper.hn_jobs import build_hn_comment_url
from app.services.profile import matches_focus_role


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


def test_bigco_targets_cover_planner_company_list() -> None:
    assert list(COMPANIES_TARGET) == [
        "JFrog",
        "Tipalti",
        "monday.com",
        "Wix",
        "Forter",
        "Paddle",
        "Sentry",
        "Mercury",
        "Rapyd",
        "Brex",
    ]
    assert COMPANIES_TARGET["Wix"] == "https://careers.wix.com/positions"


def test_parse_wix_listings_reads_role_titles_from_cards() -> None:
    html = """
    <div role="listitem">
      <div data-testid="richTextElement">
        <p><span>Senior QA Automation Engineer</span></p>
      </div>
      <a href="https://careers.wix.com/position/qa-1">Browse positions</a>
    </div>
    <div role="listitem">
      <div data-testid="richTextElement">
        <p><span>Senior QA Automation Engineer</span></p>
      </div>
      <a href="https://careers.wix.com/position/qa-1">Browse positions</a>
    </div>
    <div role="listitem">
      <div data-testid="richTextElement">
        <p><span>Frontend Engineer</span></p>
      </div>
      <a href="https://careers.wix.com/position/frontend-1">Browse positions</a>
    </div>
    """

    listings = _parse_wix_listings(
        html,
        company="Wix",
        base_url="https://careers.wix.com/positions",
    )

    assert listings == [
        (
            "https://careers.wix.com/position/qa-1",
            "Senior QA Automation Engineer",
            "Wix",
            None,
        )
    ]


def test_parse_greenhouse_jobs_filters_by_role_signal() -> None:
    listings = parse_greenhouse_jobs(
        {
            "jobs": [
                {
                    "title": "Senior QA Automation Engineer",
                    "absolute_url": "https://example.com/job/1",
                    "location": {"name": "Remote"},
                }
            ]
        },
        company="Example",
    )

    assert len(listings) == 1
    assert listings[0].title == "Senior QA Automation Engineer"
    assert listings[0].url == "https://example.com/job/1"


def test_parse_lever_jobs_extracts_title_and_url() -> None:
    listings = parse_lever_jobs(
        [
            {
                "text": "Senior QA Automation Engineer",
                "hostedUrl": "https://jobs.lever.co/example/123",
                "categories": {"location": "Remote"},
                "descriptionPlain": "Python pytest playwright API testing",
            }
        ],
        company="Example",
    )

    assert len(listings) == 1
    assert listings[0].title == "Senior QA Automation Engineer"
    assert listings[0].url == "https://jobs.lever.co/example/123"


def test_parse_ashby_jobs_reads_app_data_from_html() -> None:
    html = """
    <script>
      window.__appData = {
        "organization": {"name": "Example"},
        "jobBoard": {
          "jobPostings": [
            {
              "jobId": "ashby-1",
              "title": "Senior QA Automation Engineer",
              "isListed": true,
              "locationName": "Remote"
            }
          ]
        }
      };
    </script>
    """

    listings = parse_ashby_jobs(html, company="Fallback", base_url="https://jobs.ashbyhq.com/example")

    assert len(listings) == 1
    assert listings[0].company == "Example"
    assert listings[0].url == "https://jobs.ashbyhq.com/example?jobId=ashby-1"


def test_build_linkedin_run_inputs_generates_one_payload_per_title() -> None:
    payloads = build_linkedin_run_inputs(
        titles_csv="QA Automation Engineer,SDET",
        location="Europe",
        date_posted="r604800",
        limit_per_title=15,
        company_names_csv="OpenAI,Anthropic",
        remote_codes_csv="2,3",
    )

    assert payloads == [
        {
            "title": "QA Automation Engineer",
            "location": "Europe",
            "datePosted": "r604800",
            "companyName": ["OpenAI", "Anthropic"],
            "remote": ["2", "3"],
            "maxItems": 15,
        },
        {
            "title": "SDET",
            "location": "Europe",
            "datePosted": "r604800",
            "companyName": ["OpenAI", "Anthropic"],
            "remote": ["2", "3"],
            "maxItems": 15,
        },
    ]


def test_build_company_targets_merges_synced_careers_urls_with_defaults() -> None:
    companies = [
        CompanySnapshot(
            id="company-1",
            airtable_record_id="recWix",
            name="Wix",
            careers_url="https://jobs.wix.example/custom",
            track_fit_sdet=True,
        ),
        CompanySnapshot(
            id="company-2",
            airtable_record_id="recOpenAI",
            name="OpenAI",
            careers_url="https://openai.com/careers",
            track_fit_ai=True,
        ),
        CompanySnapshot(
            id="company-3",
            airtable_record_id="recSkipped",
            name="Skipped Co",
            careers_url="https://example.com/jobs",
        ),
    ]

    targets = _build_company_targets(companies)

    assert targets["OpenAI"] == "https://openai.com/careers"
    assert targets["Wix"] == "https://jobs.wix.example/custom"
    assert "Skipped Co" not in targets
    assert targets["Sentry"] == "https://sentry.io/careers/"


def test_posting_from_linkedin_item_maps_job_payload() -> None:
    posting = posting_from_linkedin_item(
        {
            "jobUrl": "https://www.linkedin.com/jobs/view/123",
            "title": "Senior QA Automation Engineer",
            "companyName": "Example AI",
            "descriptionText": "Python, pytest, playwright, API testing",
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


def test_matches_focus_role_rejects_manual_qa_without_python_automation() -> None:
    assert matches_focus_role("Senior QA Automation Engineer", "Python pytest playwright")
    assert not matches_focus_role("Manual QA Engineer", "Regression testing, Jira, test cases")


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
