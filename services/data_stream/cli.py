"""CLI for data stream operations."""

from __future__ import annotations

import argparse
import json
import sys

from services.common.database import get_connection


def cmd_post(args):
    with get_connection() as conn:
        from services.data_stream.post import create_post
        result = create_post(
            conn,
            location_id=args.location_id,
            post_type=args.type,
            title=args.title,
            content=args.content,
            visibility=args.visibility,
            evidence_urls=[args.evidence_url] if args.evidence_url else None,
            file_ids=[args.file_id] if args.file_id else None,
            media_type=args.media_type,
        )
        print(json.dumps(result, indent=2, default=str))


def cmd_stream(args):
    with get_connection() as conn:
        from services.data_stream.stream import get_project_stream
        posts = get_project_stream(conn, args.location_id, limit=args.limit)
        for p in posts:
            print(f"  [{p['created_at']}] [{p['post_type']}] {p['title']}")
        print(f"\n{len(posts)} posts")


def cmd_search(args):
    with get_connection() as conn:
        from services.data_stream.post import search_posts
        posts = search_posts(
            conn,
            query_text=args.query,
            location_id=args.location_id,
            limit=args.limit,
        )
        for p in posts:
            print(f"  [{p['rank']:.4f}] [{p['post_type']}] {p['title']}")
        print(f"\n{len(posts)} results")


def cmd_anchor(args):
    with get_connection() as conn:
        from services.data_stream.anchor import anchor_post
        result = anchor_post(conn, args.post_id, chain=args.chain)
        print(json.dumps(result, indent=2, default=str))


def cmd_verify(args):
    with get_connection() as conn:
        from services.data_stream.anchor import verify_post_anchoring
        result = verify_post_anchoring(conn, args.post_id)
        for k, v in result.items():
            print(f"  {k}: {v}")


def cmd_list(args):
    with get_connection() as conn:
        from services.data_stream.post import list_posts_by_project
        posts = list_posts_by_project(
            conn,
            location_id=args.location_id,
            status=args.status,
            post_type=args.type,
            limit=args.limit,
        )
        for p in posts:
            print(f"  [{p['created_at']}] [{p['status']}] [{p['post_type']}] {p['title']}")
        print(f"\n{len(posts)} posts")


def cmd_file_add(args):
    with get_connection() as conn:
        from services.data_stream.files import add_file_to_post
        result = add_file_to_post(
            conn,
            post_id=args.post_id,
            file_name=args.name,
            file_description=args.description,
            file_credit=args.credit,
            file_url=args.url,
            file_iri=args.iri,
            media_type=args.media_type,
            latitude=args.latitude,
            longitude=args.longitude,
        )
        print(json.dumps(result, indent=2, default=str))


def cmd_file_list(args):
    with get_connection() as conn:
        from services.data_stream.files import list_post_files
        files = list_post_files(conn, args.post_id)
        for f in files:
            loc = f" @ ({f['latitude']}, {f['longitude']})" if f.get("latitude") else ""
            print(f"  [{f['media_type'] or 'file'}] {f['file_name'] or 'unnamed'}{loc}")
        print(f"\n{len(files)} files")


def cmd_file_remove(args):
    with get_connection() as conn:
        from services.data_stream.files import remove_file_from_post
        removed = remove_file_from_post(conn, args.file_id)
        print(f"Removed: {removed}")


def cmd_anchor_batch(args):
    with get_connection() as conn:
        from services.data_stream.anchor import anchor_batch
        post_ids = [pid.strip() for pid in args.post_ids.split(",")]
        result = anchor_batch(conn, post_ids, chain=args.chain)
        print(json.dumps(result, indent=2, default=str))


def cmd_reconcile(args):
    with get_connection() as conn:
        from services.attestation.reconciliation import reconcile_data_stream_anchors
        result = reconcile_data_stream_anchors(conn, chain=args.chain)
        print(json.dumps(result, indent=2, default=str))


def cmd_anchoring_status(args):
    with get_connection() as conn:
        from services.attestation.reconciliation import get_anchoring_status
        result = get_anchoring_status(conn, chain=args.chain)
        print(json.dumps(result, indent=2, default=str))


def cmd_process_pending(args):
    with get_connection() as conn:
        from services.attestation.signer_service import process_pending_requests
        result = process_pending_requests(conn, chain=args.chain, limit=args.limit)
        print(json.dumps(result, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Data Stream CLI")
    sub = parser.add_subparsers(dest="command")

    p_post = sub.add_parser("post", help="Create a new data post")
    p_post.add_argument("--location-id", required=True)
    p_post.add_argument("--type", default="field_update")
    p_post.add_argument("--title", required=True)
    p_post.add_argument("--content", default=None)
    p_post.add_argument("--visibility", default="internal")
    p_post.add_argument("--evidence-url", default=None)
    p_post.add_argument("--file-id", default=None)
    p_post.add_argument("--media-type", default=None)
    p_post.set_defaults(func=cmd_post)

    p_stream = sub.add_parser("stream", help="View chronological stream")
    p_stream.add_argument("--location-id", required=True)
    p_stream.add_argument("--limit", type=int, default=50)
    p_stream.set_defaults(func=cmd_stream)

    p_search = sub.add_parser("search", help="Full-text search posts")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--location-id", default=None)
    p_search.add_argument("--limit", type=int, default=20)
    p_search.set_defaults(func=cmd_search)

    p_anchor = sub.add_parser("anchor", help="Anchor a post on-chain")
    p_anchor.add_argument("--post-id", required=True)
    p_anchor.add_argument("--chain", default="celo")
    p_anchor.set_defaults(func=cmd_anchor)

    p_verify = sub.add_parser("verify", help="Verify post anchoring")
    p_verify.add_argument("--post-id", required=True)
    p_verify.set_defaults(func=cmd_verify)

    p_list = sub.add_parser("list", help="List posts by project")
    p_list.add_argument("--location-id", required=True)
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--type", default=None)
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=cmd_list)

    # --- file commands ---
    p_file = sub.add_parser("file", help="File operations on posts")
    file_sub = p_file.add_subparsers(dest="subcommand")

    p_file_add = file_sub.add_parser("add", help="Add a file to a post")
    p_file_add.add_argument("--post-id", required=True)
    p_file_add.add_argument("--name", default=None)
    p_file_add.add_argument("--description", default=None)
    p_file_add.add_argument("--credit", default=None)
    p_file_add.add_argument("--url", default=None)
    p_file_add.add_argument("--iri", default=None)
    p_file_add.add_argument("--media-type", default=None)
    p_file_add.add_argument("--latitude", type=float, default=None)
    p_file_add.add_argument("--longitude", type=float, default=None)
    p_file_add.set_defaults(func=cmd_file_add)

    p_file_list = file_sub.add_parser("list", help="List files on a post")
    p_file_list.add_argument("--post-id", required=True)
    p_file_list.set_defaults(func=cmd_file_list)

    p_file_remove = file_sub.add_parser("remove", help="Remove a file")
    p_file_remove.add_argument("--file-id", required=True)
    p_file_remove.set_defaults(func=cmd_file_remove)

    p_anchor_batch = sub.add_parser("anchor-batch", help="Anchor multiple posts in batch")
    p_anchor_batch.add_argument("--post-ids", required=True, help="Comma-separated post IDs")
    p_anchor_batch.add_argument("--chain", default="celo")
    p_anchor_batch.set_defaults(func=cmd_anchor_batch)

    p_reconcile = sub.add_parser("reconcile", help="Reconcile DB with onchain attestation state")
    p_reconcile.add_argument("--chain", default="celo")
    p_reconcile.set_defaults(func=cmd_reconcile)

    p_status = sub.add_parser("status", help="Show anchoring pipeline status")
    p_status.add_argument("--chain", default=None)
    p_status.set_defaults(func=cmd_anchoring_status)

    p_process = sub.add_parser("process", help="Process pending attestation requests")
    p_process.add_argument("--chain", default="celo")
    p_process.add_argument("--limit", type=int, default=10)
    p_process.set_defaults(func=cmd_process_pending)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
