from uuid import uuid4

from app.models.company import CompanySnapshot
from app.services.company_sync import merge_company_records


def test_merge_company_records_is_idempotent() -> None:
    records = [
        {
            "id": "recCompany1",
            "fields": {
                "Company": "Bolt",
                "Country": "Poland",
                "Track fit SDET": True,
                "Priority": "High",
            },
        }
    ]

    existing: dict[str, CompanySnapshot] = {}
    merged, first_summary = merge_company_records(existing, records)

    assert len(merged) == 1
    assert first_summary.count_created == 1
    assert first_summary.count_updated == 0
    assert merged[0].name == "Bolt"
    assert merged[0].track_fit_sdet is True

    existing_again = {
        merged[0].airtable_record_id: CompanySnapshot(
            id=merged[0].id or str(uuid4()),
            airtable_record_id=merged[0].airtable_record_id,
            name=merged[0].name,
        )
    }
    merged_again, second_summary = merge_company_records(existing_again, records)

    assert len(merged_again) == 1
    assert second_summary.count_created == 0
    assert second_summary.count_updated == 1
    assert merged_again[0].name == "Bolt"


def test_merge_company_records_skips_missing_company_name() -> None:
    merged, summary = merge_company_records({}, [{"id": "rec1", "fields": {"Country": "UK"}}])

    assert merged == []
    assert summary.count_skipped == 1
