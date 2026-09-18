#include "linearExtrapolationFvPatchField.H"
#include "fvPatchFieldMapper.H"

template<class Type>
Foam::linearExtrapolationFvPatchField<Type>::linearExtrapolationFvPatchField
(
    const fvPatch& p,
    const DimensionedField<Type, volMesh>& iF
)
:
    calculatedFvPatchField<Type>(p, iF)
{}


template<class Type>
Foam::linearExtrapolationFvPatchField<Type>::linearExtrapolationFvPatchField
(
    const fvPatch& p,
    const DimensionedField<Type, volMesh>& iF,
    const dictionary& dict
)
:
    calculatedFvPatchField<Type>(p, iF, dict, false)
{
    evaluate();
}


template<class Type>
Foam::linearExtrapolationFvPatchField<Type>::linearExtrapolationFvPatchField
(
    const linearExtrapolationFvPatchField<Type>& ptf,
    const fvPatch& p,
    const DimensionedField<Type, volMesh>& iF,
    const fvPatchFieldMapper& mapper
)
:
    calculatedFvPatchField<Type>(ptf, p, iF, mapper)
{}


template<class Type>
Foam::linearExtrapolationFvPatchField<Type>::linearExtrapolationFvPatchField
(
    const linearExtrapolationFvPatchField<Type>& ptf,
    const DimensionedField<Type, volMesh>& iF
)
:
    calculatedFvPatchField<Type>(ptf, iF)
{}


template<class Type>
void Foam::linearExtrapolationFvPatchField<Type>::evaluate
(
    const Pstream::commsTypes
)
{
    if (!this->updated())
    {
        this->updateCoeffs();
    }

    calculatedFvPatchField<Type>::operator==(this->patchInternalField());
    calculatedFvPatchField<Type>::evaluate();
}
