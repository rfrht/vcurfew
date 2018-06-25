#!/bin/bash -x

echo "Content-type: text/plain"
echo ""


# Carrega setup inicial
source /etc/vcurfew/config.txt


# Traduz o IP para um MAC address. Sanitiza os valores.
MAC=$(arp -an | awk "match (\$0,/$REMOTE_ADDR/) {print \$4}" | tr -dc '[:xdigit:]' | tr '[:lower:]' '[:upper:]' | cut -c -12)
echo MAC vale $MAC


# Verifica se existe usuario atribuido ao MAC. Carrega variavel USER.
USER=$(sqlite $SQDB "SELECT user FROM systems WHERE mac='$MAC'")
if [ -z $USER ] ; then
   echo "MAC $MAC nao encontrado."
   exit 1
else
   echo USER $USER tem mac $MAC.
fi


# Busca quem eh usuario dono do MAC. Carrega suas configuracoes.
CONFIG=($(sqlite -separator " " $SQDB "SELECT * FROM users WHERE user='$USER'" ))
if [ -z $CONFIG ] ; then
   echo "Isso nao devia acontecer - Usuario $USER existe em systems e nao existe em users"
   exit 1
fi
echo Config vale: ${CONFIG[*]}
echo Array: USER - DUR/SEM - DUR/FDS - HR/INI - HR/FIM - TOKENS/SEM - TOKENS/FDS


# Exporta array para variaveis individuais
DURSEM=${CONFIG[1]}
DURFDS=${CONFIG[2]}
HRINI=${CONFIG[3]}
HRFIM=${CONFIG[4]}
TOKENSEM=${CONFIG[5]}
TOKENFDS=${CONFIG[6]}
HR_AGORA=$(TZ="$TIMEZONE" date +"%H")
HOJE=$(TZ="$TIMEZONE" date +"%a")
FDS="Sat Sun"


# Funcao que implementa o desbloqueio, gravacao do token e agenda desbloqueio
# para cada um dos MACs
montabloqueio() {
echo "INSERT INTO tokens VALUES ('$USER', datetime('now', 'localtime'), 1);" | sqlite /etc/vcurfew/vcurfew
for i in $(sqlite $SQDB "SELECT mac FROM systems WHERE user='$USER'" | sed 's/..\B/&:/g') ; do
   echo echo sudo /sbin/iptables -I FORWARD -i $INTERFACE -m mac --mac-source $i -j ACCEPT
   echo echo sudo /sbin/iptables -I FORWARD -i $INTERFACE -m mac --mac-source $i -j DROP >> /dev/shm/$UUID
done
echo rm /dev/shm/$UUID >> /dev/shm/$UUID
}


# Verifica se o pedido de token esta dentro do horario autorizado
if [[ $HR_AGORA -lt $HRINI || $HR_AGORA -ge $HRFIM ]] ; then
   echo Fora de horario
   exit 0
else
   echo Boa, dentro do horario permitido. Valendo.
fi


# Classifica se está valendo regra de FDS ou Dia de Semana
if [[ $FDS =~ $HOJE ]] ; then
   echo DOW: FDS
   HRS_LIBERADAS=$DURFDS
   TOKENS_AUTHORIZED=$TOKENFDS
else
   echo DOW: DISEM
   HRS_LIBERADAS=$DURSEM
   TOKENS_AUTHORIZED=$TOKENSEM
fi


# Verifica se tem token ativo
TOKEN_EPOCH=$(TZ="$TIMEZONE" sqlite $SQDB "SELECT MAX(strftime ('%s', token_epoch, )) FROM tokens WHERE token_epoch >= DATE('now', 'localtime') AND user = '$USER'" )
if [ -z $TOKEN_EPOCH ] ; then
   echo Nao emitiu token hoje, segue processamento
   echo Valor do epoch = $TOKEN_EPOCH
   let "VALIDO_ATE=$TOKEN_EPOCH+3600*$HRS_LIBERADAS"
   EPOCH_AGORA=$(date +"%s")
   let SEGUNDOS_VALIDADE="$VALIDO_ATE-$EPOCH_AGORA"
   echo Entao ficou: Agora $EPOCH_AGORA, Emitido $TOKEN_EPOCH e validade $VALIDO_ATE. Vale por mais $SEGUNDOS_VALIDADE segundos.
else
   echo Valor do epoch = $TOKEN_EPOCH
   let "VALIDO_ATE=$TOKEN_EPOCH+3600*$HRS_LIBERADAS"
   EPOCH_AGORA=$(date +"%s")
   let SEGUNDOS_VALIDADE="$VALIDO_ATE-$EPOCH_AGORA"
   echo Entao ficou: Agora $EPOCH_AGORA, Emitido $TOKEN_EPOCH e validade $VALIDO_ATE. Vale por mais $SEGUNDOS_VALIDADE segundos.
   if [[ $EPOCH_AGORA -gt $TOKEN_EPOCH && $EPOCH_AGORA -lt $VALIDO_ATE ]] ; then
      echo Tem token ativo. Saindo.
      exit 0
   fi
fi


# Verifica se tem credito para tokens
TOKENS_CONSUMED_TODAY=$(TZ="$TIMEZONE" sqlite $SQDB "SELECT COUNT(*) FROM tokens WHERE DATE(token_epoch, 'localtime') >= DATE('now', 'localtime') AND user = '$USER'")
echo Tokens usados hoje: $TOKENS_CONSUMED_TODAY
echo Tokens autorizados: $TOKENS_AUTHORIZED
if [ $TOKENS_CONSUMED_TODAY -ge $TOKENS_AUTHORIZED ] ; then
   echo "Voce consumiu sua cota do dia! Blocos autorizados: $TOKENS_AUTHORIZED, blocos consumidos: $TOKENS_CONSUMED_TODAY"
   exit 1
fi


# Liberador de token. Escolhe logica de proximo do fim do periodo de validade
UUID=$(uuid)
let "RESTANTE=$HRFIM-$HR_AGORA"
if [ $RESTANTE -le $HRS_LIBERADAS ] ; then
   echo Encerrando lojinha as $HRFIM horas.
   montabloqueio
   cat /dev/shm/$UUID | TZ=$TIMEZONE at $HRFIM:00
else
   echo Entregando token de $HRS_LIBERADAS horas, valido ate as $(TZ=$TIMEZONE date -d "+2 hours" +"%Hh%M").
   montabloqueio
   cat /dev/shm/$UUID | at NOW + 2 hours
fi

