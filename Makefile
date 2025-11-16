ifeq (,$(wildcard .env))
$(error .env file is missing at . Please create one based on .env.example)
endif

include .env	
	
build-elix:
	docker compose build

start-elix:
	docker compose up --build -d

stop-elix:
	docker compose stop