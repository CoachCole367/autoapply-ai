from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def resume(profile, job, directory):
    """Reorder verified facts by relevance without rewriting claims."""
    if not profile.verified or not profile.name or not profile.email:
        raise ValueError("A verified name and email are required")
    target = Path(directory) / "documents"
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{uuid4().hex}.pdf"
    styles = getSampleStyleSheet()
    flow = [
        Paragraph(escape(profile.name), styles["Title"]),
        Paragraph(
            escape(" | ".join(filter(None, [profile.email, profile.phone, profile.location]))),
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    skills = sorted(profile.skills, key=lambda s: s.casefold() not in job.description.casefold())
    for title, values in [
        ("Skills", skills),
        ("Experience", profile.experience),
        ("Education", profile.education),
        ("Certifications", profile.certifications),
    ]:
        if values:
            flow.append(Paragraph(title, styles["Heading2"]))
            for value in values:
                flow.extend([Paragraph(escape(value).replace("\n", "<br/>"), styles["Normal"]), Spacer(1, 6)])
    SimpleDocTemplate(str(path), title=f"{profile.name} Resume", author=profile.name).build(flow)
    return str(path.resolve())
