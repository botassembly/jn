# JN Docker Image (local build)
# For building locally after running `make build`
#
# Build: make build && docker build -t jn .
# Run:   docker run --rm -i jn cat -~csv < data.csv

FROM alpine:3.20

# Install Python and uv for Python plugins
RUN apk add --no-cache python3 py3-pip curl bash \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy pre-built binaries from local dist/
COPY dist/bin/ /usr/local/bin/
COPY jn_home/ /usr/local/lib/jn/jn_home/

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Set JN_HOME for Python plugins
ENV JN_HOME="/usr/local/lib/jn/jn_home"

# Verify installation
RUN jn --version

ENTRYPOINT ["jn"]
CMD ["--help"]
