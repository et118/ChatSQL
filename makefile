DOCKER_CMD := $(if $(shell command -v podman), podman, docker)
run:
	$(DOCKER_CMD) compose -f docker-compose.yaml -p chatsql up

clean:
	$(DOCKER_CMD) rmi -f mysql chatsql_app
