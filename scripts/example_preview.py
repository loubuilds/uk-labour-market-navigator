"""Extract the report's actual chart into a self-contained README preview."""

import re
from html import unescape
from xml.etree import ElementTree as ET


def preview(report_html, plan):
    charts = re.findall(r"<svg\b.*?</svg>", report_html, flags=re.DOTALL)
    captions = re.findall(r"<figcaption>(.*?)</figcaption>", report_html)
    if len(charts) != 1 or len(captions) != 1:
        raise ValueError("The worked example must contain one checked workforce chart")
    chart = ET.fromstring(charts[0])
    chart.attrib.update(x="30", y="102", width="840", height="220")
    chart.attrib.pop("style", None)
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": "0 0 900 390",
            "width": "900",
            "height": "390",
            "role": "img",
            "aria-labelledby": "preview-title preview-desc",
        },
    )
    ET.SubElement(root, "title", id="preview-title").text = "Chart from the fictional Sheffield hiring brief"
    ET.SubElement(root, "desc", id="preview-desc").text = (
        "The report's generated Census chart, unchanged in values and scale. "
        "Historical employed residents in a broader cross-industry occupation, not available candidates."
    )
    ET.SubElement(root, "rect", width="900", height="390", rx="14", fill="#f4f8f8")
    ET.SubElement(root, "rect", width="900", height="6", fill="#00766d")
    group = ET.SubElement(root, "g", {"font-family": "Arial, sans-serif", "fill": "#193b42"})

    def line(y, value, size="18", weight="normal"):
        ET.SubElement(group, "text", {"x": "30", "y": str(y), "font-size": size, "font-weight": weight}).text = value

    line(38, "UK LABOUR MARKET NAVIGATOR · WORKED EXAMPLE", "14", "bold")
    line(
        69,
        ", ".join(p["label"] for p in plan["scope"]["places"]) + " · " + plan["scope"]["occupation"]["label"],
        "21",
        "bold",
    )
    line(97, unescape(captions[0]), "17")
    group.append(chart)
    line(344, "Historical residents, not available candidates. Broader occupation across industries.", "16")
    line(
        371,
        "Fictional example · Source: Office for National Statistics · Read the full brief for interpretation.",
        "14",
    )
    return ET.tostring(root, encoding="unicode") + "\n"
