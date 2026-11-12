# Build environment for the mutter package: Ubuntu 24.04 with every update
# from noble-updates and noble-security and the build dependencies of the
# package, test dependencies included. build/make-image.sh copies
# mutter/debian/control into the build context.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
COPY control /tmp/deps/debian/control
RUN apt-get update \
 && apt-get -y dist-upgrade \
 && apt-get install -y --no-install-recommends build-essential dpkg-dev fakeroot \
 && apt-get build-dep -y /tmp/deps \
 && rm -rf /var/lib/apt/lists/* /tmp/deps
