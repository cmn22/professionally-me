import json

INPUT_PATH = "data/linkedin.json"
OUTPUT_PATH = "data/linkedin_clean.json"


def _date_text(date):
    return date.get("text") if date else None


def _clean_experience(exp):
    return {
        "position": exp.get("position"),
        "companyName": exp.get("companyName"),
        "employmentType": exp.get("employmentType"),
        "workplaceType": exp.get("workplaceType"),
        "location": exp.get("location"),
        "duration": exp.get("duration"),
        "startDate": _date_text(exp.get("startDate")),
        "endDate": _date_text(exp.get("endDate")),
        "description": exp.get("description"),
        "skills": exp.get("skills", []),
    }


def _clean_education(edu):
    return {
        "schoolName": edu.get("schoolName"),
        "degree": edu.get("degree"),
        "fieldOfStudy": edu.get("fieldOfStudy"),
        "period": edu.get("period"),
        "skills": edu.get("skills", []),
    }


def _clean_certification(cert):
    return {
        "title": cert.get("title"),
        "issuedAt": cert.get("issuedAt"),
        "issuedBy": cert.get("issuedBy"),
    }


def _clean_project(proj):
    return {
        "title": proj.get("title"),
        "duration": proj.get("duration"),
        "description": proj.get("description"),
    }


def _clean_recommendation(rec):
    return {
        "givenBy": rec.get("givenBy"),
        "givenByHeadline": rec.get("givenByHeadline"),
        "givenAt": rec.get("givenAt"),
        "description": rec.get("description"),
    }


def clean_profile(profile):
    location = profile.get("location", {})
    parsed_location = location.get("parsed", {})

    return {
        "name": f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
        "headline": profile.get("headline"),
        "location": parsed_location.get("text") or location.get("linkedinText"),
        "about": profile.get("about"),
        "topSkills": profile.get("topSkills"),
        "experience": [_clean_experience(e) for e in profile.get("experience", [])],
        "education": [_clean_education(e) for e in profile.get("education", [])],
        "certifications": [_clean_certification(c) for c in profile.get("certifications", [])],
        "projects": [_clean_project(p) for p in profile.get("projects", [])],
        "skills": [s["name"] for s in profile.get("skills", []) if s.get("name")],
        "languages": profile.get("languages", []),
        "receivedRecommendations": [_clean_recommendation(r) for r in profile.get("receivedRecommendations", [])],
    }


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    profiles = data if isinstance(data, list) else [data]
    cleaned = [clean_profile(p) for p in profiles]
    result = cleaned[0] if len(cleaned) == 1 else cleaned

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    original_chars = len(json.dumps(data))
    cleaned_chars = len(json.dumps(result))
    reduction = (1 - cleaned_chars / original_chars) * 100
    print(f"Written to {OUTPUT_PATH}")
    print(f"Size: {original_chars:,} → {cleaned_chars:,} chars ({reduction:.0f}% reduction)")


if __name__ == "__main__":
    main()
