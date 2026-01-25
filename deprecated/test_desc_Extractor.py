from __future__ import annotations

import json
from fluxer.extractors.desc_extractor import DescriptionExtractor


SAMPLE_URLS = [
    {
        "title": "Hisense HMAS2008BP 20L 800W Compact Microwave",
        "source": "the good guys",
        "url": "https://www.thegoodguys.com.au/hisense-483l-french-door-refrigerator-hrcd483tbw",
    },
    {
        "title": "Anko 20L Compact Microwave",
        "source": "the good guys",
        "url": "https://www.thegoodguys.com.au/omega-altise-brigadier-25mj-ng-sand-dune-heater-oabrfngsd",
    },
    {
        "title": "LG NeoChef 23L Smart Inverter Microwave Oven MS2336DB",
        "source": "JB Hi-Fi",
        "url": "https://www.jbhifi.com.au/products/lg-neochef-ms2336db-23l-smart-inverter-microwave",
    },
    {
        "title": "SOLT GGSOMW20B 20L 700W Microwave",
        "source": "The Good Guys",
        "url": "https://www.thegoodguys.com.au/solt-20l-700w-microwave-black-ggsomw20b",
    },
    {
        "title": "Kogan 20L Microwave",
        "source": "Kogan.com",
        "url": "https://www.strandbags.com.au/collections/handbags/products/evity-alana-leather-canvas-crossbody-bag-3223877?variant=45359501738142",
    },
]


def main() -> None:
    # Test WITHOUT max_cost to see what it actually costs
    extractor = DescriptionExtractor(debug=True, timeout_s=60, max_cost="unlimited")
    # result = extractor.extract("https://httpbin.org/html")


    results = []

    for item in SAMPLE_URLS:
        print(f"\n=== Testing: {item['title']} ({item['source']}) ===")
        try:
            result = extractor.extract(item["url"])
        except Exception as e:
            print("EXTRACT_FAIL", item["url"], "err=", repr(e))
            continue


        print("URL:", item["url"])
        print("Method:", result.method)
        print("Meta Title:", result.meta_title or "❌ Not found")
        print("Meta Description:", result.meta_description or "❌ Not found")
        print("Description found:", bool(result.description))

        if result.description:
            print("Preview:")
            print(result.description[:400], "...\n")
        else:
            print("❌ No description extracted\n")

        results.append(
            {
                "title": item["title"],
                "source": item["source"],
                "url": item["url"],
                "method": result.method,
                "meta_title": result.meta_title,
                "meta_description": result.meta_description,
                "description": result.description,
            }
        )

    print("\n=== JSON OUTPUT ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
