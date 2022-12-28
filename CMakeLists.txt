cmake_minimum_required(VERSION 3.16)

project(pike VERSION 1.0 LANGUAGES C)

set(CLIENT_SRC src/client.c)
set(SERVER_SRC src/server.c)

add_executable(client ${CLIENT_SRC})
add_executable(server ${SERVER_SRC})
