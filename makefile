DOCKER_CMD := $(if $(shell command -v podman), podman, docker)
run:
	$(DOCKER_CMD) compose -f docker-compose.yaml -p mariadb up

clean:
	$(DOCKER_CMD) compose -f docker-compose.yaml -p mariadb down
