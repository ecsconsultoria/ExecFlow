"""Sanity checks no catálogo RBAC.

Garante que toda permissão atribuída a uma role existe no catálogo
canônico — bloqueia typos como `quotes.edit` vs `quote.edit`.
"""
from __future__ import annotations
from app.utils.permissions import (
    ALL_PERMS,
    PERMISSION_CATALOG,
    ROLE_PERMISSION_MATRIX,
)


def test_catalog_has_no_duplicates():
    codes = [c for (c, *_rest) in PERMISSION_CATALOG]
    assert len(codes) == len(set(codes)), "Permissões duplicadas no catálogo"


def test_role_perms_are_subset_of_catalog():
    for role, perms in ROLE_PERMISSION_MATRIX.items():
        unknown = set(perms) - ALL_PERMS
        assert not unknown, f"Role {role} tem perms fora do catálogo: {sorted(unknown)}"


def test_admin_has_all_perms():
    assert set(ROLE_PERMISSION_MATRIX["ADMIN"]) == ALL_PERMS


def test_viewer_has_only_view_perms():
    viewer = set(ROLE_PERMISSION_MATRIX["VIEWER"])
    non_view = {p for p in viewer if not (p.endswith(".view") or p == "dashboard.view")}
    # VIEWER pode ter algumas perms calculadas; só garantimos que não há .edit/.delete/.create
    forbidden_suffix = (".edit", ".delete", ".create", ".cancel", ".approve",
                        ".invoice", ".close", ".reopen", ".manage")
    leaked = {p for p in non_view if p.endswith(forbidden_suffix)}
    assert not leaked, f"VIEWER tem perms de mutação: {sorted(leaked)}"
