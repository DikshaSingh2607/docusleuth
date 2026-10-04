#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ABSTENTION = 'I could not find this in the uploaded documents.'


def recall_at_k(retrieved: list[str], gold: set[str], k: int) -> float | None:
    if not gold:
        return None
    return len(set(retrieved[:k]) & gold) / len(gold)


def groundedness(answer: str, cited_numbers: set[int]) -> float | None:
    if not answer.strip():
        return None
    if answer.strip() == ABSTENTION:
        return 1.0
    sentences = [part.strip() for part in answer.replace('!', '.').replace('?', '.').split('.') if part.strip()]
    if not sentences:
        return None
    grounded = sum(any(f'[{number}]' in sentence for number in cited_numbers) for sentence in sentences)
    return grounded / len(sentences)


def classification_metrics(predicted: set[str], gold: set[str]) -> dict[str, int | float]:
    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': precision, 'recall': recall}


def abstention_accuracy(predicted: list[bool], gold: list[bool]) -> float | None:
    if not gold or len(predicted) != len(gold):
        return None
    return sum(actual == expected for actual, expected in zip(predicted, gold)) / len(gold)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate DocuSleuth against user-provided real fixtures.')
    parser.add_argument('--fixtures', type=Path, default=Path('tests/fixtures'))
    parser.add_argument('--report', type=Path, default=Path('tests/reports/evaluation.json'))
    args = parser.parse_args()
    reasons: list[str] = []
    root = args.fixtures
    key = root / 'README_TEST_KEY.md'
    manifest_candidates = [root / 'gold_labels.json', root / 'gold.json', root / 'manifest.json']
    manifest = next((path for path in manifest_candidates if path.exists()), None)
    if not root.exists():
        reasons.append(f'fixture directory missing: {root}')
    if not key.exists():
        reasons.append('README_TEST_KEY.md is not attached under the fixture directory')
    if not manifest:
        reasons.append('no supported gold-label manifest found (gold_labels.json, gold.json, or manifest.json)')
    report: dict[str, Any] = {'status': 'blocked' if reasons else 'measured', 'reasons': reasons}
    if not reasons and manifest:
        data = load_json(manifest)
        retrieval = data.get('retrieval', [])
        recalls = [recall_at_k(item.get('retrieved_chunk_ids', []), set(item.get('gold_chunk_ids', [])), int(item.get('k', 5))) for item in retrieval]
        recalls = [value for value in recalls if value is not None]
        answers = data.get('answers', [])
        grounded = [groundedness(item.get('answer', ''), set(item.get('cited_numbers', []))) for item in answers]
        grounded = [value for value in grounded if value is not None]
        conflicts = data.get('conflicts', {})
        abstentions = data.get('abstentions', {})
        report['metrics'] = {
            'retrieval_recall_at_k': sum(recalls) / len(recalls) if recalls else None,
            'answer_groundedness': sum(grounded) / len(grounded) if grounded else None,
            'conflict': classification_metrics(set(conflicts.get('predicted', [])), set(conflicts.get('gold', []))),
            'abstention_accuracy': abstention_accuracy(abstentions.get('predicted', []), abstentions.get('gold', [])),
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'measured' else 2


if __name__ == '__main__':
    raise SystemExit(main())
