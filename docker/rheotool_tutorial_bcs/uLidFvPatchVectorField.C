#include "uLidFvPatchVectorField.H"
#include "addToRunTimeSelectionTable.H"
#include "volFields.H"

Foam::uLidFvPatchVectorField::uLidFvPatchVectorField
(
    const fvPatch& p,
    const DimensionedField<vector, volMesh>& iF
)
:
    fixedValueFvPatchVectorField(p, iF)
{}


Foam::uLidFvPatchVectorField::uLidFvPatchVectorField
(
    const fvPatch& p,
    const DimensionedField<vector, volMesh>& iF,
    const dictionary& dict
)
:
    fixedValueFvPatchVectorField(p, iF, dict)
{}


Foam::uLidFvPatchVectorField::uLidFvPatchVectorField
(
    const uLidFvPatchVectorField& ptf,
    const fvPatch& p,
    const DimensionedField<vector, volMesh>& iF,
    const fvPatchFieldMapper& mapper
)
:
    fixedValueFvPatchVectorField(ptf, p, iF, mapper)
{}


Foam::uLidFvPatchVectorField::uLidFvPatchVectorField
(
    const uLidFvPatchVectorField& ptf,
    const DimensionedField<vector, volMesh>& iF
)
:
    fixedValueFvPatchVectorField(ptf, iF)
{}


void Foam::uLidFvPatchVectorField::updateCoeffs()
{
    if (updated())
    {
        return;
    }

    const scalar& t = this->db().time().timeOutputValue();
    const vectorField& x = patch().Cf();

    vectorField::operator=
    (
        vector(1, 0, 0)
      * 8.0
      * (1.0 + Foam::tanh(8.0*(t - 0.5)))
      * Foam::pow(x.component(0), 2.0)
      * Foam::pow(1.0 - x.component(0), 2.0)
    );

    fixedValueFvPatchVectorField::updateCoeffs();
}


void Foam::uLidFvPatchVectorField::write(Ostream& os) const
{
    fvPatchVectorField::write(os);
    writeEntry(os, "value", *this);
}


namespace Foam
{
    makePatchTypeField
    (
        fvPatchVectorField,
        uLidFvPatchVectorField
    );
}
