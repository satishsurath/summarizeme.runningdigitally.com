# Use TimescaleDB PG17 which includes PGAI pre-installed
FROM timescale/timescaledb-ha:pg17

USER root

# Ensure plpython3u is available (PGAI dependency)
# TimescaleDB images already include it

# Create the ai extension if not present
RUN [ -f /usr/share/postgresql/17/extension/ai--1.0.sql ] || \
    (pip install pgai && python3 -c "import pgai; print('pgai installed')" && \
     find / -name 'ai.control' 2>/dev/null)

