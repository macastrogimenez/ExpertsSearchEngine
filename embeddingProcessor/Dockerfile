FROM eclipse-temurin:21-jdk AS build
WORKDIR /workspace

COPY gradlew settings.gradle gradle.properties ./
COPY gradle/ gradle/
COPY app/build.gradle app/build.gradle
COPY app/src/main/ app/src/main/

# installDist includes the application launcher and all runtime dependencies.
# Integration tests need running services and are run separately.
RUN chmod +x gradlew && ./gradlew --no-daemon :app:installDist

FROM eclipse-temurin:21-jre
WORKDIR /app

COPY --from=build --chown=10001:10001 /workspace/app/build/install/app/ ./
USER 10001:10001

ENTRYPOINT ["/app/bin/app"]
