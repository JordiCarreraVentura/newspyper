#!/bin/sh

REPOS_DIR="/Users/jordi/Documents/Ideas/Consejos/Cacharrería/cámaras acorazadas de Obsidian/repos"
FINAL_DIR="/Users/jordi/Laboratorio/Python/newspyper"
BATCH_SIZE=10

cd "$REPOS_DIR" || exit 1

count=0

for repo in */ ; do
  (
    echo
    echo "$repo"
    cd "$REPOS_DIR/$repo" || exit 1
    git pull
  ) &

  count=$((count + 1))

  if [ "$count" -eq "$BATCH_SIZE" ]; then
    wait
    count=0

    sleep_time=$(awk 'BEGIN { srand(); print int(3 + rand() * 8) }')
    echo
    echo "Sleeping $sleep_time seconds before next batch..."
    sleep "$sleep_time"
  fi
done

wait

cd "$FINAL_DIR" || exit 1
make run