#!/bin/bash
# Script de configuration du bucket S3 pour les sauvegardes OPCP

BUCKET_NAME="ai-OPCP"
REGION="eu-west-3"  # Paris

echo "🚀 Configuration du bucket S3 pour les sauvegardes OPCP"
echo "=================================================="

# Vérifier si AWS CLI est installé
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI n'est pas installé"
    echo "   Installation: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Vérifier si AWS est configuré
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI n'est pas configuré"
    echo "   Exécutez: aws configure"
    exit 1
fi

echo "✅ AWS CLI configuré"

# Créer le bucket s'il n'existe pas
echo ""
echo "📦 Création du bucket s3://${BUCKET_NAME}..."

if aws s3 ls "s3://${BUCKET_NAME}" 2>&1 | grep -q 'NoSuchBucket'; then
    aws s3 mb "s3://${BUCKET_NAME}" --region "${REGION}"
    echo "✅ Bucket créé"
else
    echo "ℹ️  Le bucket existe déjà"
fi

# Activer le versioning
echo ""
echo "🔄 Activation du versioning..."
aws s3api put-bucket-versioning \
    --bucket "${BUCKET_NAME}" \
    --versioning-configuration Status=Enabled
echo "✅ Versioning activé"

# Activer le chiffrement par défaut
echo ""
echo "🔒 Activation du chiffrement..."
aws s3api put-bucket-encryption \
    --bucket "${BUCKET_NAME}" \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            },
            "BucketKeyEnabled": true
        }]
    }'
echo "✅ Chiffrement activé"

# Configurer la lifecycle policy
echo ""
echo "♻️  Configuration de la lifecycle policy..."
cat > /tmp/lifecycle-policy.json << 'EOF'
{
    "Rules": [
        {
            "Id": "TransitionToIA",
            "Status": "Enabled",
            "Prefix": "",
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "GLACIER"
                }
            ]
        },
        {
            "Id": "DeleteOldBackups",
            "Status": "Enabled",
            "Prefix": "",
            "Expiration": {
                "Days": 365
            }
        }
    ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
    --bucket "${BUCKET_NAME}" \
    --lifecycle-configuration file:///tmp/lifecycle-policy.json

rm /tmp/lifecycle-policy.json
echo "✅ Lifecycle policy configurée (Glacier après 30j, suppression après 365j)"

# Bloquer l'accès public
echo ""
echo "🔐 Blocage de l'accès public..."
aws s3api put-public-access-block \
    --bucket "${BUCKET_NAME}" \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
echo "✅ Accès public bloqué"

echo ""
echo "=================================================="
echo "✅ Configuration terminée!"
echo ""
echo "Bucket S3: s3://${BUCKET_NAME}"
echo "Région: ${REGION}"
echo ""
echo "Vous pouvez maintenant utiliser:"
echo "  python scripts/backup_database.py"
echo ""
