#!/bin/bash
# 2018-12-11
#
# Script which will generate a hucon.run file.
#
# Author: Sascha.MuellerzumHagen@baslerweb.com

BASEDIR=`dirname "${0}"`
cd "$BASEDIR"

# compress the needed files into one tar image
echo $1 > __version__
tar -czvf hucon.tar.gz __version__ README.md code/ install.sh python_lib/ start_server.sh uninstall.sh update.sh webserver/

# generate a self extracting tar image
tmp=__extract__$RANDOM

printf "#!/bin/bash
PAYLOAD_LINE=\`awk '/^__PAYLOAD_BELOW__/ {print NR + 1; exit 0; }' \$0\`

# Install tar to decompress the image.
opkg install tar

path=/root/hucon
if [ \$1 ]; then
    path=\"\$1\"hucon
fi

mkdir -p \$path | tail -n+\$PAYLOAD_LINE \$0 | tar -xvzC \$path

sh \$path/install.sh

exit 0
__PAYLOAD_BELOW__\n" > "$tmp"

cat "$tmp" "hucon.tar.gz" > "hucon.run" && rm "$tmp" && rm "hucon.tar.gz" && rm __version__
chmod +x "hucon.run"