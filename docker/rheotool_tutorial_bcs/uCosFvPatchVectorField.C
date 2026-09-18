#include "uCosFvPatchVectorField.H"
#include "addToRunTimeSelectionTable.H"
#include "volFields.H"

Foam::uCosFvPatchVectorField::uCosFvPatchVectorField
(
    const fvPatch& p,
    const DimensionedField<vector, volMesh>& iF
)
:
    fixedValueFvPatchVectorField(p, iF),
    tlim_(1),
    fac_(1),
    uav_(0, 0, 0),
    dirN_(1, 0, 0)
{}


Foam::uCosFvPatchVectorField::uCosFvPatchVectorField
(
    const fvPatch& p,
    const DimensionedField<vector, volMesh>& iF,
    const dictionary& dict
)
:
    fixedValueFvPatchVectorField(p, iF),
    tlim_(readScalar(dict.lookup("tlim"))),
    fac_(readScalar(dict.lookup("fac"))),
    uav_(dict.lookup("uav")),
    dirN_(dict.lookup("dirN"))
{
    updateCoeffs();
}


Foam::uCosFvPatchVectorField::uCosFvPatchVectorField
(
    const uCosFvPatchVectorField& ptf,
    const fvPatch& p,
    const DimensionedField<vector, volMesh>& iF,
    const fvPatchFieldMapper& mapper
)
:
    fixedValueFvPatchVectorField(ptf, p, iF, mapper),
    tlim_(ptf.tlim_),
    fac_(ptf.fac_),
    uav_(ptf.uav_),
    dirN_(ptf.dirN_)
{}


Foam::uCosFvPatchVectorField::uCosFvPatchVectorField
(
    const uCosFvPatchVectorField& ptf,
    const DimensionedField<vector, volMesh>& iF
)
:
    fixedValueFvPatchVectorField(ptf, iF),
    tlim_(ptf.tlim_),
    fac_(ptf.fac_),
    uav_(ptf.uav_),
    dirN_(ptf.dirN_)
{}


void Foam::uCosFvPatchVectorField::updateCoeffs()
{
    if (updated())
    {
        return;
    }

    const scalar t = this->db().time().timeOutputValue();

    vector Ut = uav_;

    if (t <= tlim_)
    {
        Ut = (((1 - Foam::cos(constant::mathematical::pi*t))/fac_)*dirN_);
    }

    vectorField::operator=(Ut);

    fixedValueFvPatchVectorField::updateCoeffs();
}


void Foam::uCosFvPatchVectorField::write(Ostream& os) const
{
    fvPatchVectorField::write(os);
    os.writeKeyword("tlim") << tlim_ << token::END_STATEMENT << nl;
    os.writeKeyword("fac") << fac_ << token::END_STATEMENT << nl;
    os.writeKeyword("uav") << uav_ << token::END_STATEMENT << nl;
    os.writeKeyword("dirN") << dirN_ << token::END_STATEMENT << nl;
    writeEntry(os, "value", *this);
}


namespace Foam
{
    makePatchTypeField
    (
        fvPatchVectorField,
        uCosFvPatchVectorField
    );
}
