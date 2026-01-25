"""Debug HTML structure to see what's being extracted."""

from bs4 import BeautifulSoup

HTML = """
<div class="_1bkzdz98 _1bkzdz99">
    <div>
        <div class="_1wda3xa0"></div>
        <div class="bfao0i0">
            <p><strong>Key Features</strong></p>
            <p><strong>Sleek Minimalist Design</strong><br>The tempered glass on the front door creates a modern, stylish appearance.</p>
            <p><strong>Anti-Bacterial Coating</strong><br>The Anti-Bacterial EasyClean™ interior coating makes cleaning simple and convenient.</p>
        </div>
    </div>
</div>
"""

soup = BeautifulSoup(HTML, 'html.parser')

print("All <p> tags found:")
print("=" * 80)

all_paragraphs = soup.find_all('p')
for i, para in enumerate(all_paragraphs, 1):
    print(f"\nParagraph {i}:")
    print(f"  Full text: {para.get_text(' ', strip=True)}")

    print(f"  Children:")
    for content in para.children:
        if isinstance(content, str):
            print(f"    - String: '{content.strip()}'")
        else:
            print(f"    - Tag {content.name}: '{content.get_text(' ', strip=True)}'")

print("\n" + "="*80)
print("\nNow testing extraction logic:")
print("="*80)

processed_texts = set()
paragraph_texts = []

for para in all_paragraphs:
    # Get direct text content
    para_text_parts = []
    for content in para.children:
        if isinstance(content, str):
            para_text_parts.append(content.strip())
        elif content.name in ['strong', 'b', 'em', 'i', 'br']:
            para_text_parts.append(content.get_text(' ', strip=True))

    para_text = ' '.join(para_text_parts).strip()

    if para_text and len(para_text) > 10:
        para_text_lower = para_text.lower()
        if para_text_lower not in processed_texts:
            processed_texts.add(para_text_lower)
            paragraph_texts.append(para_text)
            print(f"\n[ADDED] {para_text}")

print("\n" + "="*80)
print(f"\nFinal result ({len(paragraph_texts)} paragraphs):")
print("="*80)
for i, text in enumerate(paragraph_texts, 1):
    print(f"{i}. {text}")
