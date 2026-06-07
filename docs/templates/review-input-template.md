# Review Input Template

Use this template to structure your review input materials for AudienceLens.

## JSON Format

```json
{
  "title": "[Name of the product/game/concept being reviewed]",
  "description": "[One-sentence description of what this is]",
  "materials": [
    {
      "type": "text",
      "description": "[Material content or summary]"
    },
    {
      "type": "screenshot",
      "description": "[Description of screenshot content]",
      "path": "[File path or URL]"
    },
    {
      "type": "url",
      "description": "[URL to be fetched and analyzed]"
    }
  ]
}
```

## Markdown Format

```markdown
# [Review Subject Title]

## Description
[One-sentence description]

## Materials

### Material 1: [Name]
**Type**: text/screenshot/url
**Content**:
[Paste content or describe material]

### Material 2: [Name]
**Type**: screenshot
**Path**: [file path]
**Description**: [What this screenshot shows]
```

## Task Type Reference

### Game Review (synthetic-playtest)
| Task Type | Description |
|-----------|-------------|
| `steam_page_review` | Steam store page review |
| `demo_first_play` | Demo first-play experience |
| `concept_review` | Game concept review |
| `monetization_review` | Monetization model review |
| `landing_page_review` | Landing page review |
| `social_media_post` | Social media post review |
| `video_ad_review` | Video ad review |

### Product Review (audience-panel)
| Task Type | Description |
|-----------|-------------|
| `product_review` | Product overall review |
| `app_review` | App review |
| `website_review` | Website review |
| `feature_feedback` | Feature feedback |
| `pricing_review` | Pricing review |
| `ux_audit` | UX audit |

## Tips

- Include as much material as possible — more evidence leads to better reviews
- Screenshots and URLs are more valuable than text descriptions alone
- Specify the task type if you know it — otherwise AudienceLens will infer
- Use `--depth full` for important reviews, `--depth quick` for initial screening
