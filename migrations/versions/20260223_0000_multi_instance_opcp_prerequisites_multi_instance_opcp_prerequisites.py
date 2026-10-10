"""multi instance opcp prerequisites

Turns the single, implicit OPCP prerequisites space into named Installations.
Creates the ``installations`` table, seeds a ``Default_Installation``, backfills
existing content/answers into it, resolves cross-user answer collisions
(last-updated wins), then enforces the new per-installation uniqueness keys.

Revision ID: multi_instance_opcp_prereq
Revises: add_account_security_2fa_fields
Create Date: 2026-02-23

"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'multi_instance_opcp_prereq'
down_revision = 'add_account_security_2fa_fields'
branch_labels = None
depends_on = None


# Fixed UUID for the seeded Default_Installation so the backfill can reference it
# deterministically (Req 7.1).
DEFAULT_INSTALLATION_ID = '00000000-0000-0000-0000-000000000001'


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == 'postgresql'


def upgrade() -> None:
    is_pg = _is_postgresql()
    uuid_default = text('gen_random_uuid()') if is_pg else None

    # ------------------------------------------------------------------
    # 1. installations table (matches app/models/installation.py)
    # ------------------------------------------------------------------
    op.create_table(
        'installations',
        sa.Column(
            'id', sa.Uuid(),
            server_default=uuid_default,
            nullable=False,
        ),
        sa.Column('project_name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    # ------------------------------------------------------------------
    # 2. Seed the Default_Installation with a fixed id (Req 7.1)
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            "INSERT INTO installations "
            "(id, project_name, created_at, updated_at, created_by, updated_by) "
            "VALUES (:id, :name, :created_at, :updated_at, NULL, NULL)"
        ).bindparams(
            id=DEFAULT_INSTALLATION_ID,
            name='Default Installation',
            # Bind a concrete timestamp value. ``sa.func.now()`` is a SQL
            # expression and cannot be sent as a driver-level bind parameter
            # (it raises "type 'now' is not supported"/"can't adapt type" on
            # every backend); a real datetime binds portably.
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    # ------------------------------------------------------------------
    # 3. Add installation_id to both tables as NULLABLE first so existing
    #    rows survive the ADD COLUMN (Req 7.2, 7.3).
    # ------------------------------------------------------------------
    op.add_column(
        'prerequisite_content',
        sa.Column('installation_id', sa.Uuid(), nullable=True),
    )
    op.add_column(
        'prerequisite_answers',
        sa.Column('installation_id', sa.Uuid(), nullable=True),
    )

    # ------------------------------------------------------------------
    # 4. Backfill existing rows into the Default_Installation (Req 7.2, 7.3)
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            "UPDATE prerequisite_content SET installation_id = :id"
        ).bindparams(id=DEFAULT_INSTALLATION_ID)
    )
    op.execute(
        sa.text(
            "UPDATE prerequisite_answers SET installation_id = :id"
        ).bindparams(id=DEFAULT_INSTALLATION_ID)
    )

    # ------------------------------------------------------------------
    # 5. Resolve answer collisions before applying the new unique key.
    #    Previously answers were distinct per user_id; collapsing to
    #    (installation_id, slug, row_id) can produce duplicates. Keep the
    #    most-recently-updated row per key (Req 7.4).
    # ------------------------------------------------------------------
    if is_pg:
        op.execute(
            """
            DELETE FROM prerequisite_answers a
            USING (
              SELECT id,
                     ROW_NUMBER() OVER (
                       PARTITION BY installation_id, slug, row_id
                       ORDER BY updated_at DESC, id DESC
                     ) AS rn
              FROM prerequisite_answers
            ) ranked
            WHERE a.id = ranked.id AND ranked.rn > 1
            """
        )
    else:
        # SQLite / other: DELETE ... USING is unsupported. Use a correlated
        # subquery delete on the ranked CTE to the same effect.
        op.execute(
            """
            DELETE FROM prerequisite_answers
            WHERE id IN (
              SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                         PARTITION BY installation_id, slug, row_id
                         ORDER BY updated_at DESC, id DESC
                       ) AS rn
                FROM prerequisite_answers
              ) ranked
              WHERE ranked.rn > 1
            )
            """
        )

    # ------------------------------------------------------------------
    # 6. prerequisite_answers: drop per-user scoping artifacts.
    # ------------------------------------------------------------------
    with op.batch_alter_table('prerequisite_answers') as batch_op:
        batch_op.drop_constraint(
            'uq_prerequisite_answers_user_slug_row', type_='unique'
        )
        batch_op.drop_index('idx_prerequisite_answers_user_slug')
        batch_op.drop_constraint(
            'fk_prerequisite_answers_user_id', type_='foreignkey'
        )
        batch_op.drop_column('user_id')

    # ------------------------------------------------------------------
    # 7. prerequisite_content: replace the slug PK with a surrogate id UUID PK.
    #    slug stays as a NOT NULL, indexed column.
    # ------------------------------------------------------------------
    op.add_column(
        'prerequisite_content',
        sa.Column(
            'id', sa.Uuid(),
            server_default=uuid_default,
            nullable=True,
        ),
    )
    if is_pg:
        # Populate the surrogate id for existing rows, then swap the PK.
        op.execute("UPDATE prerequisite_content SET id = gen_random_uuid() WHERE id IS NULL")
        op.execute("ALTER TABLE prerequisite_content DROP CONSTRAINT prerequisite_content_pkey")
        op.alter_column('prerequisite_content', 'id', nullable=False)
        op.create_primary_key(
            'pk_prerequisite_content', 'prerequisite_content', ['id']
        )
    else:
        # SQLite has no gen_random_uuid(); populate the surrogate id for
        # existing rows in Python before enforcing NOT NULL, otherwise the
        # batch recreate fails the id NOT NULL constraint on backfilled rows.
        bind = op.get_bind()
        existing = bind.execute(
            sa.text("SELECT slug FROM prerequisite_content WHERE id IS NULL")
        ).fetchall()
        for (slug_value,) in existing:
            bind.execute(
                sa.text(
                    "UPDATE prerequisite_content SET id = :new_id WHERE slug = :slug"
                ).bindparams(new_id=uuid.uuid4().hex, slug=slug_value)
            )
        # SQLite: rebuild the table via batch to move the primary key onto id.
        with op.batch_alter_table(
            'prerequisite_content',
            recreate='always',
        ) as batch_op:
            batch_op.alter_column('id', nullable=False)
            batch_op.create_primary_key('pk_prerequisite_content', ['id'])

    # ------------------------------------------------------------------
    # 8. Enforce the new schema: installation_id NOT NULL, FKs with
    #    ON DELETE CASCADE, the new unique keys, and supporting indexes.
    # ------------------------------------------------------------------
    with op.batch_alter_table('prerequisite_content') as batch_op:
        batch_op.alter_column('installation_id', existing_type=sa.Uuid(), nullable=False)
        batch_op.create_foreign_key(
            'fk_prerequisite_content_installation_id',
            'installations', ['installation_id'], ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_unique_constraint(
            'uq_prerequisite_content_installation_slug',
            ['installation_id', 'slug'],
        )
        batch_op.create_index(
            'ix_prerequisite_content_installation_id', ['installation_id'], unique=False
        )

    with op.batch_alter_table('prerequisite_answers') as batch_op:
        batch_op.alter_column('installation_id', existing_type=sa.Uuid(), nullable=False)
        batch_op.create_foreign_key(
            'fk_prerequisite_answers_installation_id',
            'installations', ['installation_id'], ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_unique_constraint(
            'uq_prerequisite_answers_installation_slug_row',
            ['installation_id', 'slug', 'row_id'],
        )
        batch_op.create_index(
            'idx_prerequisite_answers_installation_slug',
            ['installation_id', 'slug'], unique=False,
        )
        batch_op.create_index(
            'ix_prerequisite_answers_installation_id', ['installation_id'], unique=False
        )


def downgrade() -> None:
    is_pg = _is_postgresql()

    # ------------------------------------------------------------------
    # Reverse step 8: drop new indexes / unique keys / FKs on both tables.
    # ------------------------------------------------------------------
    with op.batch_alter_table('prerequisite_answers') as batch_op:
        batch_op.drop_index('ix_prerequisite_answers_installation_id')
        batch_op.drop_index('idx_prerequisite_answers_installation_slug')
        batch_op.drop_constraint(
            'uq_prerequisite_answers_installation_slug_row', type_='unique'
        )
        batch_op.drop_constraint(
            'fk_prerequisite_answers_installation_id', type_='foreignkey'
        )

    with op.batch_alter_table('prerequisite_content') as batch_op:
        batch_op.drop_index('ix_prerequisite_content_installation_id')
        batch_op.drop_constraint(
            'uq_prerequisite_content_installation_slug', type_='unique'
        )
        batch_op.drop_constraint(
            'fk_prerequisite_content_installation_id', type_='foreignkey'
        )

    # ------------------------------------------------------------------
    # Reverse step 7: restore slug PK on content, drop the surrogate id.
    # ------------------------------------------------------------------
    if is_pg:
        op.execute("ALTER TABLE prerequisite_content DROP CONSTRAINT pk_prerequisite_content")
        op.drop_column('prerequisite_content', 'id')
        op.create_primary_key(
            'prerequisite_content_pkey', 'prerequisite_content', ['slug']
        )
    else:
        with op.batch_alter_table(
            'prerequisite_content',
            recreate='always',
        ) as batch_op:
            batch_op.drop_column('id')
            batch_op.create_primary_key('prerequisite_content_pkey', ['slug'])

    # ------------------------------------------------------------------
    # Reverse steps 3-6: drop installation_id from content; restore the
    # per-user answer shape. Per-installation rows that cannot be
    # represented per-user are discarded (matches the per_user migration).
    # ------------------------------------------------------------------
    op.drop_column('prerequisite_content', 'installation_id')

    op.execute("DELETE FROM prerequisite_answers")

    with op.batch_alter_table('prerequisite_answers') as batch_op:
        batch_op.drop_column('installation_id')
        batch_op.add_column(sa.Column('user_id', sa.Uuid(), nullable=False))
        batch_op.create_foreign_key(
            'fk_prerequisite_answers_user_id',
            'users', ['user_id'], ['id'],
        )
        batch_op.create_index(
            'idx_prerequisite_answers_user_slug',
            ['user_id', 'slug'], unique=False,
        )
        batch_op.create_unique_constraint(
            'uq_prerequisite_answers_user_slug_row',
            ['user_id', 'slug', 'row_id'],
        )

    # ------------------------------------------------------------------
    # Reverse steps 1-2: drop the installations table.
    # ------------------------------------------------------------------
    op.drop_table('installations')
