import sqlalchemy as sa


metadata = sa.MetaData()


synopsis_generations = sa.Table(
    "synopsis_generations",
    metadata,

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
