import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB


metadata = sa.MetaData()


story_projects = sa.Table(
    "story_projects",
    metadata,

    sa.Column(
        "id",
        sa.BigInteger(),
        primary_key=True,
        autoincrement=True,
    ),

    sa.Column(
        "title",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "premise",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "genre",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "style",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "language",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "memory",
        JSONB(),
        nullable=False,
        server_default=sa.text(
            "'{}'::jsonb"
        ),
    ),

    sa.Column(
        "memory_version",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),

    sa.Column(
        "created_at",
        sa.DateTime(
            timezone=True,
        ),
        nullable=False,
        server_default=sa.text(
            "now()"
        ),
    ),

    sa.Column(
        "updated_at",
        sa.DateTime(
            timezone=True,
        ),
        nullable=False,
        server_default=sa.text(
            "now()"
        ),
    ),
)


synopsis_generations = sa.Table(
    "synopsis_generations",
    metadata,

    sa.Column(
        "story_id",
        sa.BigInteger(),
        sa.ForeignKey(
            "story_projects.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    ),

    sa.Column(
        "thread_id",
        sa.Text(),
        nullable=True,
    ),

    sa.Column(
        "user_request",
        sa.Text(),
        nullable=True,
    ),

    sa.Column(
        "entry_summary",
        sa.Text(),
        nullable=True,
    ),

    sa.Column(
        "id",
        sa.BigInteger(),
        primary_key=True,
        autoincrement=True,
    ),

    sa.Column(
        "idea",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "genre",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "style",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "language",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "requested_length",
        sa.Text(),
        nullable=False,
    ),

    sa.Column(
        "selected_writer",
        sa.Text(),
        nullable=True,
    ),

    sa.Column(
        "draft",
        sa.Text(),
        nullable=True,
    ),

    sa.Column(
        "final_text",
        sa.Text(),
        nullable=True,
    ),

    sa.Column(
        "critique_passed",
        sa.Boolean(),
        nullable=True,
    ),

    sa.Column(
        "critique_score",
        sa.Integer(),
        nullable=True,
    ),

    sa.Column(
        "revision_count",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),

    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
)


story_memory_versions = sa.Table(
    "story_memory_versions",
    metadata,

    sa.Column(
        "id",
        sa.BigInteger(),
        primary_key=True,
        autoincrement=True,
    ),

    sa.Column(
        "story_id",
        sa.BigInteger(),
        sa.ForeignKey(
            "story_projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    ),

    sa.Column(
        "version",
        sa.Integer(),
        nullable=False,
    ),

    sa.Column(
        "memory",
        JSONB(),
        nullable=False,
    ),

    sa.Column(
        "source_generation_id",
        sa.BigInteger(),
        sa.ForeignKey(
            "synopsis_generations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    ),

    sa.Column(
        "created_at",
        sa.DateTime(
            timezone=True,
        ),
        nullable=False,
        server_default=sa.text(
            "now()"
        ),
    ),

    sa.UniqueConstraint(
        "story_id",
        "version",
        name=(
            "uq_story_memory_"
            "story_version"
        ),
    ),
)
